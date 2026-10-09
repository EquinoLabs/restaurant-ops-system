# ROMS — Cloudflare R2 Image Storage Implementation Specification

**Document version:** 1.0  
**Date:** 10 October 2026  
**Status:** Implementation guidance — inspect the current repository before coding  
**Scope:** Public food/menu images and restaurant branding assets  
**Primary stack:** React + Vite + TypeScript, FastAPI, SQLAlchemy 2.x, Alembic, Neon PostgreSQL, Cloudflare R2

---

## 1. Purpose

Implement a reliable, low-cost image-storage and delivery path for the Restaurant Operations Management System (ROMS).

Use Cloudflare R2 to store image files, Neon PostgreSQL to store application records and object keys, FastAPI to authorize and handle uploads, and a configured public image domain to serve public menu images directly to browsers.

The design should work for the current release without introducing unnecessary infrastructure. It should leave room for more outlets, businesses, images, and traffic later.

### Explicitly in scope

- Food/menu item images.
- Restaurant/business logos and other public branding assets.
- A backend service for uploading and deleting R2 objects.
- Persisting object keys in PostgreSQL.
- Returning usable public image URLs in menu API responses.
- Configuration, validation, tests, and documentation.
- Safe handling of existing `image_url` data, if present.

### Explicitly out of scope for this implementation

- Redis or another cache service.
- Image transformations or a dedicated image-processing pipeline.
- Video uploads.
- Private document storage or audit-log archiving.
- Presigned GET URLs for public menu images.
- Direct browser-to-R2 uploads, unless the existing project has a strong reason to use them.
- Reworking unrelated menu, QR, order, payment, or authentication functionality.

Do not implement out-of-scope items speculatively.

---

## 2. Architecture decision

### Decision

Use **Cloudflare R2 for image files** and **Neon PostgreSQL for structured application data**.

Store an R2 **object key** in PostgreSQL, not the complete public URL. FastAPI derives the public URL from a configured base URL and the stored key when preparing API responses.

Example object key:

`businesses/{business_id}/outlets/{outlet_id}/menu-items/{item_id}/{unique_id}.webp`

Example configured public base URL:

`https://images.example.com`

Example derived URL:

`https://images.example.com/businesses/biz_123/outlets/outlet_456/menu-items/item_789/abc123.webp`

The example domain and IDs are illustrative. Do not use them as real deployment values.

### Why store the object key?

- The database does not become coupled to a particular domain.
- A public image domain can be changed without rewriting every menu record.
- The object key can be used for authorized replacement and deletion.
- R2 remains the file store; PostgreSQL remains the source of truth for application records.
- The public URL is a delivery address, not the image's database identity.

### Important distinction

An object key is not a URL. Constructing a URL in code does not itself make an object publicly readable. The chosen public domain must be configured to serve the relevant R2 bucket, and the bucket/domain access policy must be verified.

Use a Cloudflare R2 custom domain for production public image delivery. Do not assume the development `r2.dev` URL can be constructed from the account ID and bucket name. Use the actual configured URL from Cloudflare. Keep development and production domains configurable.

---

## 3. Request and data flow

### A. Upload flow

1. An authorized restaurant/business administrator selects an image in the React admin interface.
2. React sends the file as multipart form data to a FastAPI endpoint.
3. FastAPI authenticates the caller and checks that they have permission to manage the relevant business/outlet.
4. FastAPI validates the upload:
   - Enforce a conservative configurable maximum file size.
   - Allow only supported raster image formats.
   - Validate the actual file content, not just the client-provided MIME type or filename extension.
   - Reject malformed files and unsupported formats.
   - Consider pixel/dimension limits to mitigate decompression bombs and oversized images.
5. FastAPI generates a unique, safe object key. Never use a client-supplied filename as the object key.
6. The R2 service uploads the file using the S3-compatible API.
7. The application saves the object key in the appropriate database record using SQLAlchemy.
8. The API returns the record and/or the derived public image URL to the frontend.
9. React displays the returned image URL.

Handle the failure case where the R2 upload succeeds but the database write fails. Best-effort delete the newly uploaded object and log a safe diagnostic message. Do not expose credentials, signed headers, or sensitive provider responses to the client.

### B. Public menu read flow

1. A customer scans an outlet QR code and opens the existing public menu.
2. React calls the current public menu endpoint.
3. FastAPI queries active menu items and their stored image keys.
4. The response serializer derives the public URL using the configured image base URL.
5. React renders the returned image URL using a normal `<img>` element or the project's existing image component.
6. The browser requests the image directly from the public image domain. FastAPI should not proxy every public image request.

For an item with no image, return `null` (or preserve the existing response contract) and show the frontend's existing/default placeholder.

### C. Delete or replace flow

1. Authenticate the administrator and authorize access to the relevant item or asset.
2. Determine the old key from the database record. Do not accept an arbitrary object key from the client and delete it without ownership checks.
3. For replacement, upload to a new unique key first.
4. Update the database record to the new key.
5. After the database update succeeds, delete the old object as a best-effort operation.
6. If deletion fails, log it for later cleanup; do not make the image record point to a deleted object.
7. For a normal deletion, remove or clear the database reference and delete the associated object in a controlled sequence, with failure handling and observability.

Use unique/versioned object keys for replacements so browser/CDN caches do not continue showing an old image at the same URL.

---

## 4. Object-key convention and ownership

Prefer an organized key scheme such as:

- `businesses/{business_id}/outlets/{outlet_id}/menu-items/{menu_item_id}/{uuid}.webp`
- `businesses/{business_id}/branding/{uuid}.webp`

Adapt this to the actual ROMS entity relationships. If menu items belong directly to an outlet in the current schema, follow that model rather than inventing a new hierarchy.

Rules:

- Use UUIDs or another collision-resistant generated component.
- Never trust a supplied filename as a path.
- Do not put secrets, access tokens, personal data, or sensitive information in keys or custom metadata.
- Object-key prefixes are organizational only. They are not an authorization boundary.
- Enforce ownership and outlet/business permissions in FastAPI before uploading, replacing, or deleting an object.
- Avoid storing redundant ownership metadata in R2 unless it serves a concrete operational purpose; the application database should establish ownership.

---

## 5. Database model and API contract

### Database

Before modifying the schema, inspect the current SQLAlchemy models, Alembic migrations, and response schemas.

If the current field is called `image_url`, determine whether it contains:
- object keys only,
- complete public URLs,
- or a mixture.

Do not blindly rename or reinterpret existing values. If the field contains object keys despite its name, consider a planned migration to `image_key` only if it is safe and useful for the current release. If it contains real URLs or mixed historical values, create a deliberate compatibility/migration plan and test it. Preserve existing QR/menu behavior.

For new or changed schema:
- Use a nullable string field for an optional object key.
- Select a reasonable length based on the project's schema conventions.
- Add a database migration through Alembic.
- Do not use `Base.metadata.create_all()` as a production schema-management strategy.
- Avoid a migration if the existing field and API contract already work and a rename would add risk without immediate value.

### Public API response

Prefer a response field such as `image_url` for the frontend, even if the database stores `image_key`. This separates storage implementation from the frontend contract.

Example response:

```json
{
  "id": "item_123",
  "name": "Paneer Tikka",
  "price": "280.00",
  "image_url": "https://images.example.com/businesses/biz_123/outlets/outlet_456/menu-items/item_123/abc.webp"
}
```

The example is illustrative. Match actual project response schemas and price conventions.

If the public menu API currently returns `image_url`, preserve that frontend-facing field unless a coordinated API change is necessary. The database field and API field do not have to share the same name.

### URL construction

- Read the public base URL from backend environment configuration, e.g. `R2_PUBLIC_BASE_URL`.
- Normalize the base URL once during configuration loading.
- Join the base URL and key safely, avoiding duplicate or missing slashes.
- Do not let client input select an arbitrary host/domain.
- Do not construct the public URL from account IDs or bucket names unless that is explicitly the configured URL format.
- Never expose the R2 account ID, access key, secret, or internal endpoint as a public image URL.
- If the key is null, return a null image URL.
- Avoid blindly accepting stored absolute URLs as keys. Define explicit compatibility handling if legacy rows contain full URLs.

---

## 6. Backend implementation guidance

Inspect the current backend package structure and conventions before deciding exact file paths. A reasonable separation is:

- `api/.../r2_client.py`: low-level S3-compatible R2 client and object operations.
- `api/.../image_storage_service.py`: upload validation, object-key construction, URL derivation, and application-level operations.
- Existing router: authenticated admin upload/replace/delete endpoints.
- Existing public menu service/serializer: attach derived public URLs to menu items.
- Existing settings/config module: read and validate environment configuration.

Do not create duplicate service layers if the repository already has suitable abstractions. Fit the project's existing layout.

### Client and library

The existing implementation used `boto3`, which is compatible with R2's S3 API. Reuse it if the project already depends on it and it is a good fit. Do not add a second storage SDK without a concrete reason.

`boto3` calls are synchronous. If they are invoked from an `async def` FastAPI route/service, avoid blocking the event loop. Use the project's established thread-pool pattern or use a synchronous route/service consistently where appropriate. Do not simply mark a blocking call `async` and assume it is non-blocking.

Create the R2 client lazily or through the project's application lifecycle/configuration pattern if required, so missing production credentials do not unexpectedly break unrelated imports or tests. Follow existing dependency-injection and test conventions.

### Environment variables

Use server-side variables such as:

```dotenv
R2_ACCOUNT_ID=replace_with_account_id
R2_ACCESS_KEY_ID=replace_with_access_key_id
R2_SECRET_ACCESS_KEY=replace_with_secret_access_key
R2_BUCKET_NAME=replace_with_bucket_name
R2_PUBLIC_BASE_URL=https://images.example.com
R2_MAX_IMAGE_BYTES=5242880
```

These are examples; the 5 MiB limit is a conservative starting point, not a universal requirement. Confirm product needs and existing upload constraints before fixing it.

Rules:
- Never commit real secrets.
- Add placeholders to the appropriate backend `.env.example`.
- Do not use `VITE_` variables for R2 credentials. Anything exposed through a Vite-prefixed variable is public to the browser.
- Keep separate credentials/configuration for development and production.
- Validate required configuration when image-storage functionality is initialized or used.
- Never print secrets in logs or return them in API errors.

### S3-compatible client

Use an endpoint of the form:

`https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com`

Use the correct bucket name and credentials from environment configuration, the `auto` region setting supported by the R2 S3-compatible configuration, and SigV4 signing. Confirm configuration against current Cloudflare documentation and the project's installed `boto3` version.

### Upload implementation requirements

- Generate object keys on the server.
- Read or stream uploads with bounded memory use.
- Validate both file size and actual image content.
- Set the correct `Content-Type` metadata when uploading.
- Set appropriate `Cache-Control` headers for immutable, uniquely keyed public assets where suitable.
- Do not set public-read ACLs blindly; public access should be configured through the bucket/custom-domain setup.
- Return the object key internally and derive the public URL separately.
- Map expected provider errors to safe application errors; do not return raw exception text to clients.
- Log sufficient operational context (operation, business/outlet ID, object key or a safe identifier, error category) without logging secrets or file contents.

### Deletion

- Delete only keys associated with a verified application record and authorized business/outlet.
- Handle missing objects according to an explicit idempotent policy.
- Avoid bare `except:` blocks that silently hide all errors.
- If deletion fails after a database change, report/record the failure for cleanup rather than claiming the file was removed.
- Do not make deletion of an image an authorization bypass.

---

## 7. Public access, domain, and caching

### Public image domain

Before production use:
1. Create/select an R2 bucket.
2. Configure the intended custom domain in Cloudflare for the bucket.
3. Verify the domain is active and serves a test image.
4. Configure `R2_PUBLIC_BASE_URL` with that exact domain.
5. Test an object URL from a browser without application credentials.
6. Confirm that private buckets/documents are not accidentally exposed.

Do not invent a domain or assume the domain is already configured. If this setup is not complete, support local tests with a fake URL builder and leave production configuration pending. Do not make account or DNS changes without explicit user approval.

### Caching

- Use a unique object key when an image changes.
- Configure suitable `Cache-Control` headers for immutable public assets.
- Let browsers and Cloudflare cache public images.
- No Redis is required for image delivery.
- Avoid short-lived presigned GET URLs for public menu images.
- Do not introduce a custom image proxy or transformation service in this release.

The menu JSON response may have its own cache policy, separate from the image files. Price and availability must be revalidated by the backend during future order creation; an image cache is not a source of business truth.

---

## 8. Frontend implementation guidance

- Use the public `image_url` supplied by the API.
- Do not expose R2 access keys, secret keys, or private bucket credentials in React.
- Do not generate S3 signatures in the browser.
- Display a placeholder if the URL is null or the image fails to load.
- Use lazy loading for menu images below the fold (`loading="lazy"`), with sensible dimensions/aspect ratios to reduce layout shifts.
- Preserve the existing QR menu's appearance and behavior.
- If an admin upload is added, show progress/loading state, validation errors, success feedback, and a preview.
- Do not assume an upload succeeded until the backend confirms it.
- Avoid retaining an old cached image URL after replacement; unique keys should normally give the new image a new URL.

---

## 9. Security requirements

- Only authorized users can upload, replace, or delete business/outlet assets.
- Verify business/outlet membership and permissions on every mutating endpoint.
- Do not trust `user_id`, `business_id`, `outlet_id`, item ID, MIME type, or filename from the client without validating them against authenticated context and database records.
- Validate actual file signatures/decoding, size, and dimensions.
- Restrict supported formats to those the frontend and storage pipeline can serve safely (e.g. JPEG, PNG, WebP; include GIF only if product requirements justify it).
- Prevent path traversal by generating object keys internally and never joining arbitrary client paths.
- Keep R2 secrets in backend environment variables only.
- Do not log signed URLs or credentials.
- Do not store private business documents in the public image bucket.
- Public food images/logos may be readable by anyone, so do not put confidential content there.

---

## 10. Failure handling and consistency

R2 and PostgreSQL do not share a distributed transaction. Implement deliberate best-effort compensation:

### Upload then database write
- Upload object.
- Attempt database update/insert.
- If the database write fails, try to delete the just-uploaded object.
- Log cleanup failure for manual or scheduled cleanup.

### Replace existing image
- Upload new object with a new key.
- Update the database reference.
- Only then delete the old object.
- If the database update fails, delete the new object if possible and retain the old database reference/object.

### Delete image
- Verify record ownership.
- Clear/delete the database reference according to current product behavior.
- Delete the old object and record/log failures for retry.
- Choose ordering carefully to avoid a database record pointing at a missing object. Document the chosen failure behavior.

Do not build a general-purpose job queue solely for these rare cases in the first release. Clear logging and a documented manual cleanup path are sufficient initially.

---

## 11. Tests and acceptance criteria

Follow the project's existing test structure and conventions.

### Unit tests
- Correct public URL construction with and without trailing slashes.
- Null key produces a null URL.
- Generated keys are unique and do not use unsafe client filenames.
- Invalid MIME/content, malformed images, oversized files, and unsupported formats are rejected.
- Provider errors become safe application errors.
- Existing API response shape remains compatible.

### Service/router tests
- Authorized upload stores the object and the expected key.
- Unauthorized user cannot upload, replace, or delete assets for another business/outlet.
- Public menu response returns a derived URL for an item with an image.
- Public menu response returns null/placeholder-compatible data when no image exists.
- Failed database write triggers best-effort object cleanup.
- Failed deletion is logged/handled according to the defined policy.
- Existing QR menu and menu API tests still pass.

Mock R2/S3 calls in automated tests. Unit tests must not require real Cloudflare credentials or alter a live bucket.

### Manual verification
When credentials and domain configuration are ready:
- Upload a small valid image.
- Confirm the object exists in the intended R2 bucket.
- Confirm PostgreSQL stores only the object key, not an expiring presigned URL.
- Open the derived URL in a private/incognito browser session to confirm public delivery works.
- Verify a menu image renders on desktop and mobile.
- Replace an image and verify the new version appears.
- Verify an unauthorized user cannot alter another outlet's images.
- Verify secrets are absent from frontend bundles, logs, API responses, and Git.

### Testing workflow
- During implementation, run the smallest relevant test suite.
- Run broader/full tests after the task is complete or when shared/global functionality changes materially.
- Do not run the full suite after every small edit.
- Do not deploy, change production DNS/domain settings, create/delete production buckets, rotate credentials, or run migrations against production without explicit approval.

---

## 12. Existing implementation and migration precautions

The previous project used `boto3`, uploaded to an R2 object key, saved metadata, and generated presigned URLs for private objects. The reusable idea is **store the object key, generate a URL at response time**.

Do not copy the previous code verbatim. Known areas to improve:
- It manually constructed an `r2.dev` URL from bucket/account information; configure and verify the real public base URL instead.
- Synchronous `boto3` calls were invoked inside async methods; prevent event-loop blocking.
- It read the entire file into memory; keep memory use bounded.
- It trusted client-provided MIME types too much; validate actual content.
- Broad exception handlers suppressed useful failures.
- Its in-memory presigned URL cache is not needed for public images and is per-process, not shared.
- It used user-oriented key prefixes; ROMS should use its actual business/outlet/item ownership model.

Before implementation, inspect:
- Current `MenuItem` model and its image field.
- Existing Alembic migrations and current database schema.
- Public menu response schema and serializer/service.
- Current admin routes and authorization model.
- Existing dependency and configuration files.
- Existing tests and frontend image rendering.

Preserve current working QR/menu behavior. Do not rename fields or migrate data unless the inspection establishes that a change is needed and the migration is planned and tested.

---

## 13. Required implementation process for the coding agent

1. **Inspect first.** Summarize the existing model, migrations, API contract, auth/permissions, frontend use of image fields, and test locations.
2. **Report the data shape.** State whether current image data is null, object keys, full URLs, or mixed.
3. **Propose a minimal change plan.** Identify exact files to change and whether a migration is required.
4. **Wait if a consequential decision is needed.** Do not make live Cloudflare account/domain changes, production migrations, or destructive data changes without approval.
5. **Implement only the current agreed scope.** Reuse existing project patterns; avoid unrelated refactoring.
6. **Test incrementally.** Run the smallest relevant tests first and broader tests at completion.
7. **Report clearly.** List changed files, configuration needed, migrations (if any), tests run/results, manual steps remaining, and any risks.

### Definition of done

- Image object keys are stored reliably in PostgreSQL.
- The API derives a public URL from a configured base domain.
- The frontend can render public images directly from the image domain.
- Uploads are authorized and validated.
- Object-store failures are handled safely.
- Existing menu/QR functionality remains intact.
- Tests cover URL generation, validation, permissions, and failure paths.
- No credentials or production infrastructure changes are introduced without approval.
- No Redis, image proxy, or unrelated infrastructure is added.
