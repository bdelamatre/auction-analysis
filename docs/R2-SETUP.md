# Cloudflare R2 setup

The lot photographs are 2.06 GB across 5,222 files — 93% of everything in `data/`.
They are the reason this repo is heavy, and they are the one part of it that never
changes once scraped. So they live in R2 and everything else stays in git.

| | Size | Lives in |
|---|---|---|
| `data/*/lots/*/images/` | 2.06 GB | **R2** |
| `lot.html` captures (1,500) | 132 MB | git |
| catalog pages (77) | 16 MB | git |
| `meta.json` (1,500), `lots.csv`, `lot-urls.txt` | 10 MB | git |

The HTML captures stay in git deliberately: they compress and delta well, they are
the provenance record for every verdict, and 148 MB is a clone you can still wait
through. Only the images are worth externalising.

---

## 1. Credentials (once)

In the Cloudflare dashboard: **R2 → API → Manage API tokens → Create API token**.

- Permission: **Object Read & Write**
- Scope it to this bucket only, not the whole account
- The **Secret Access Key is displayed exactly once.** Copy it now.

You want the **Access Key ID / Secret Access Key** pair, not the long single-string
"API token" shown above them. The S3 endpoint only understands the key pair.

Your account ID is the 32-hex-character string in the S3 API endpoint on that same
page — `https://<account-id>.r2.cloudflarestorage.com`. It is not the bucket name.

Then, in the repo:

```sh
cp .env.r2.example .env.r2
$EDITOR .env.r2          # fill in the four values
```

`.env.r2` is gitignored. It is the single source of truth for both the sync script
and your S3 browser.

---

## 2. The repo side

Install rclone (`brew install rclone`, or `curl https://rclone.org/install.sh | sudo bash`).
Needs v1.59+; older builds return 401 against R2.

rclone rather than the AWS CLI because it diffs all 5,222 files before transferring
anything, resumes a broken run without re-uploading, and sidesteps R2's CRC32
checksum incompatibility (see Troubleshooting).

```sh
scripts/r2.sh check     # verify credentials, reach the bucket, count both sides
scripts/r2.sh status    # dry run — exactly what push and pull would change
scripts/r2.sh push      # upload images to R2
scripts/r2.sh pull      # download images from R2 into data/
```

`push` mirrors: anything under `data/` on R2 that is not present locally gets
deleted. `pull` only copies — it will never delete a local file. Run `status`
first if you are unsure.

No secret is ever written to an rclone config file; the script defines the remote
through `RCLONE_CONFIG_R2_*` environment variables for the life of the process.

### Fresh clone

```sh
git clone <repo> && cd auction-analysis
cp .env.r2.example .env.r2 && $EDITOR .env.r2
scripts/r2.sh pull
```

Pull before working in the gallery. `summer-grandeur-2026.html` points its `<img>` tags
at `data/{day}/lots/{slug}/images/`, so it needs the local copies to render offline on a
phone with bad signal — that was the whole point of using local paths over Invaluable's
CDN.

---

## 3. The S3 browser side

`scripts/r2.sh browser` prints these filled in with your account ID and bucket.

| Setting | Value |
|---|---|
| Provider / type | **S3 (Amazon S3 compatible)** — use the generic S3 profile, not an AWS one |
| Endpoint / server | `<account-id>.r2.cloudflarestorage.com` |
| Port | 443 (TLS) |
| Region | `auto` |
| Access Key ID | `R2_ACCESS_KEY_ID` |
| Secret Access Key | `R2_SECRET_ACCESS_KEY` |
| Addressing style | **path-style** |
| Signature version | **v4** |

App specifics:

- **Cyberduck / Mountain Duck** — new bookmark, protocol *Amazon S3*, put the endpoint
  hostname in **Server**. If the token is scoped to one bucket, also set **Path** to the
  bucket name under *More Options*, otherwise the initial listing fails.
- **S3 Browser (Windows)** — Add Account, type *S3 Compatible Storage*, REST endpoint =
  the hostname, tick **Use secure transfer (SSL/TLS)**. Under Advanced set signature
  version to v4 and addressing to path-style.
- **WinSCP** — File protocol *Amazon S3*, host name = the endpoint hostname, port 443.
- **Transmit (macOS)** — server type *S3*, server = endpoint hostname, leave region `auto`.
- **RcloneView / rclone rcd** — reuses whatever rclone remote you configure.

Two things reliably go wrong:

**"No buckets found" after a successful connect.** A bucket-scoped token cannot call
`ListBuckets`. This is correct behaviour, not a misconfiguration. Point the app
directly at the bucket path instead of browsing to it.

**Signature errors.** Almost always virtual-hosted addressing or a region other than
`auto`. R2 wants path-style and `auto`.

---

## 4. Cutting over

The images are still tracked in git right now, and `.git` is 2.7 GB. Adding them to
`.gitignore` stops *future* commits but does not shrink an existing clone — the blobs
are already in history.

Do it in this order, and do not skip the verify:

```sh
scripts/r2.sh push                      # 1. upload
scripts/r2.sh check                     # 2. confirm the remote count matches local
git rm -r --cached 'data/*/lots/*/images'   # 3. untrack, keeps files on disk
git commit -m "Move lot images to R2"
```

After step 3 the working copy and R2 are the only full copies. That is why step 2 is
not optional.

Step 3 stops the repo growing but leaves the 2.7 GB history intact, so clones stay
slow. Actually reclaiming it means rewriting history with `git filter-repo` and
force-pushing — which invalidates every existing clone and any open PR. That is a
separate decision; nothing above depends on it.

---

## 5. Troubleshooting

**`Header 'x-amz-checksum-algorithm' with value 'CRC32' not implemented`** — recent AWS
SDKs and AWS CLI v2 send CRC32 integrity checksums by default and R2 rejects them.
rclone is unaffected. If you use the AWS CLI directly:

```sh
export AWS_REQUEST_CHECKSUM_CALCULATION=WHEN_REQUIRED
export AWS_RESPONSE_CHECKSUM_VALIDATION=WHEN_REQUIRED
```

or pass `--checksum-algorithm CRC32` per command.

**401 Unauthorized** — rclone older than 1.59, or the account ID in the endpoint is
wrong. Check `rclone version`.

**403 on some objects, 200 on others** — the token is read-only. Object Read & Write
is needed for `push`.

**`SignatureDoesNotMatch`** — a trailing space or newline pasted into
`R2_SECRET_ACCESS_KEY`.

---

Sources: [Cloudflare R2 — rclone](https://developers.cloudflare.com/r2/examples/rclone/),
[Cloudflare R2 — aws CLI](https://developers.cloudflare.com/r2/examples/aws/aws-cli/),
[R2 error codes](https://developers.cloudflare.com/r2/api/error-codes/).
