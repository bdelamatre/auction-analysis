#!/usr/bin/env php
<?php
/**
 * thomaston-scrape.php
 *
 * Archives a Thomaston Place Auction Galleries sale: every paginated catalog
 * page, every individual lot page, and every lot image.
 *
 * The site is a Next.js front end (Invaluable's "pl-next" platform) sitting
 * behind Cloudflare, with Algolia-backed pagination in a double-encoded query
 * string. It is server-rendered, so plain HTTP works -- but the UA has to look
 * like a browser and the crawl has to be slow enough not to trip bot rules.
 *
 * Usage:
 *   php thomaston-scrape.php probe <lot-url>     Inspect one lot, print what
 *                                                the extractors found. Do this
 *                                                FIRST before a full run.
 *   php thomaston-scrape.php run [options]       Full crawl.
 *   php thomaston-scrape.php status [options]    Show crawl progress. Reads
 *                                                only local files.
 *   php thomaston-scrape.php report [options]    Build lots.csv from what is
 *                                                already on disk.
 *
 * Options:
 *   --days=1,2,3        Which days to crawl (default: all)
 *   --out=./data        Output root (default: ./data)
 *   --delay=2.0         Seconds between requests (default: 2.0)
 *   --jitter=0.75       Random extra delay, 0..N seconds (default: 0.75)
 *   --limit=N           Stop after N lots per day (for testing)
 *   --no-images         Skip image downloads
 *   --include-all-images  Keep every image variant, including adjacent lots'
 *                       carousel thumbnails. Only needed if the filter misfires.
 *   --no-lots           Catalog pages only
 *   --force             Re-download files that already exist
 *   --verify            On resume, decode each cached image and re-fetch any
 *                       that are corrupt. Slower start, safer archive.
 *   --ua="..."          Override user agent
 *   --cainfo=PATH       Override the CA bundle used for TLS verification.
 *
 * TLS on Windows: PHP usually ships with no CA bundle, so HTTPS fails with
 * "unable to get local issuer certificate". Simply drop cacert.pem
 * (https://curl.se/ca/cacert.pem) in the same folder as this script and it is
 * picked up automatically -- no php.ini edit needed.
 *
 * Resume is automatic: anything already on disk is skipped unless --force.
 * Ctrl-C at any point and re-run the same command to pick up where you left off.
 *
 * Requires: php-cli with curl, dom, json, mbstring.
 */

declare(strict_types=1);

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const HOST = 'https://live.thomastonauction.com';

const CATALOGS = [
    '1' => ['slug' => 'summer-grandeur-2026_EJ9YVYG7L8',   'label' => 'day1'],
    '2' => ['slug' => 'summer-grandeur-day-2_LKAXYN98L3',  'label' => 'day2'],
    '3' => ['slug' => 'summer-grandeur-day-3_LGFHI3LMWB',  'label' => 'day3'],
];

// The Algolia index name embedded in the pagination parameter. If Thomaston
// changes the default sort this will change too -- check a paginated URL in
// your browser's address bar and update.
const ALGOLIA_INDEX = 'upcoming_lots_lotNumber_asc_prod';

const DEFAULT_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                 . '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';

const MAX_ATTEMPTS          = 4;    // per URL
const MAX_CONSECUTIVE_BLOCK = 5;    // consecutive Cloudflare blocks before abort
const MIN_HTML_BYTES        = 4000; // smaller than this = probably a challenge page
const IMAGE_HOST            = 'image.invaluable.com';

// curl errors that will never succeed on retry -- fail fast with advice instead
// of burning four attempts and 30 seconds on each URL.
const FATAL_CURL_ERRORS = [
    60 => 'TLS certificate could not be verified. PHP on Windows ships without a CA '
        . "bundle.\n  Fix: download https://curl.se/ca/cacert.pem and set curl.cainfo "
        . "in php.ini,\n  or pass --cainfo=C:/path/to/cacert.pem to this script.",
    77 => 'CA bundle file could not be read -- check the path in curl.cainfo.',
    51 => 'TLS certificate or host mismatch.',
    6  => 'DNS lookup failed -- check the hostname and your connection.',
];

// ---------------------------------------------------------------------------
// Option parsing
// ---------------------------------------------------------------------------

$argvCopy = $argv;
array_shift($argvCopy);
$command = array_shift($argvCopy) ?: 'help';

$opt = [
    'days'   => '1,2,3',
    'out'    => './data',
    'delay'  => '2.0',
    'jitter' => '0.75',
    'limit'  => '0',
    'ua'     => DEFAULT_UA,
    'cainfo' => '',
];
$flags = ['no-images' => false, 'no-lots' => false, 'force' => false,
          'include-all-images' => false, 'verify' => false];
$positional = [];

foreach ($argvCopy as $arg) {
    if (preg_match('/^--([a-z-]+)=(.*)$/s', $arg, $m)) {
        $opt[$m[1]] = $m[2];
    } elseif (preg_match('/^--([a-z-]+)$/', $arg, $m) && array_key_exists($m[1], $flags)) {
        $flags[$m[1]] = true;
    } else {
        $positional[] = $arg;
    }
}

$OUT    = rtrim($opt['out'], '/');
$DELAY  = (float) $opt['delay'];
$JITTER = (float) $opt['jitter'];
$LIMIT  = (int) $opt['limit'];
$UA     = $opt['ua'];
$FORCE  = $flags['force'];

if ($opt['cainfo'] !== '' && !is_file($opt['cainfo'])) {
    fwrite(STDERR, "--cainfo file not found: {$opt['cainfo']}\n");
    exit(1);
}
$CAINFO = resolveCaBundle($opt['cainfo']);

/**
 * Decide which CA bundle to hand libcurl.
 *
 * Order: explicit --cainfo, then cacert.pem sitting next to this script, then
 * the working directory, then whatever php.ini already configures (returning ''
 * leaves curl to its own defaults). PHP on Windows normally ships without a CA
 * bundle at all, so dropping cacert.pem beside the script keeps the whole job
 * self-contained and portable between machines.
 */
function resolveCaBundle(string $explicit): string
{
    if ($explicit !== '') {
        return $explicit;
    }
    foreach ([__DIR__ . '/cacert.pem', getcwd() . '/cacert.pem'] as $candidate) {
        if (is_file($candidate) && filesize($candidate) > 50_000) {
            return $candidate;
        }
    }
    return ''; // fall back to php.ini / system store
}

// ---------------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------------

$consecutiveBlocks = 0;
$cookieJar = sys_get_temp_dir() . '/thomaston-cookies.txt';

/**
 * Fetch a URL with retries, exponential backoff and Cloudflare-block detection.
 * Returns ['status' => int, 'body' => string, 'error' => ?string].
 */
function fetchUrl(string $url, bool $binary = false): array
{
    global $UA, $cookieJar, $consecutiveBlocks, $DELAY, $JITTER, $CAINFO;

    $attempt = 0;
    $lastError = null;

    while ($attempt < MAX_ATTEMPTS) {
        $attempt++;

        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_MAXREDIRS      => 5,
            CURLOPT_CONNECTTIMEOUT => 15,
            CURLOPT_TIMEOUT        => $binary ? 120 : 45,
            CURLOPT_ENCODING       => '',           // accept gzip/br
            CURLOPT_USERAGENT      => $UA,
            CURLOPT_COOKIEJAR      => $cookieJar,
            CURLOPT_COOKIEFILE     => $cookieJar,
            CURLOPT_HTTPHEADER     => [
                'Accept: ' . ($binary
                    ? 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
                    : 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
                'Accept-Language: en-US,en;q=0.9',
                'Upgrade-Insecure-Requests: 1',
                'Sec-Fetch-Dest: ' . ($binary ? 'image' : 'document'),
                'Sec-Fetch-Mode: navigate',
                'Sec-Fetch-Site: none',
            ],
        ]);

        if ($CAINFO !== '') {
            curl_setopt($ch, CURLOPT_CAINFO, $CAINFO);
        }

        $body     = curl_exec($ch);
        $status   = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $expected = (int) curl_getinfo($ch, CURLINFO_CONTENT_LENGTH_DOWNLOAD);
        $err      = curl_error($ch);
        $errno    = curl_errno($ch);
        curl_close($ch);

        if ($body === false) {
            if (isset(FATAL_CURL_ERRORS[$errno])) {
                fwrite(STDERR, "\nFATAL: $err\n  " . FATAL_CURL_ERRORS[$errno] . "\n");
                exit(3);
            }
            $lastError = $err ?: 'curl failed';
            backoff($attempt);
            continue;
        }

        // Cloudflare challenge / block detection
        if (in_array($status, [403, 503], true) && looksLikeChallenge((string) $body)) {
            $consecutiveBlocks++;
            if ($consecutiveBlocks >= MAX_CONSECUTIVE_BLOCK) {
                fwrite(STDERR, "\n\nABORTING: Cloudflare is blocking this client repeatedly.\n"
                    . "Options: raise --delay well above 2s, run from a different IP, or switch\n"
                    . "to a headless browser (Playwright/Puppeteer) which can solve the challenge.\n");
                exit(2);
            }
            $lastError = "cloudflare challenge (HTTP $status)";
            backoff($attempt + 2); // back off harder on challenges
            continue;
        }

        if ($status === 429) {
            $lastError = 'rate limited (429)';
            backoff($attempt + 2);
            continue;
        }

        if ($status >= 500) {
            $lastError = "server error ($status)";
            backoff($attempt);
            continue;
        }

        // Short read: the server told us how many bytes to expect and we got
        // fewer. Retry rather than persist a truncated file.
        if ($expected > 0 && strlen((string) $body) < $expected) {
            $lastError = sprintf('truncated response (%d of %d bytes)',
                strlen((string) $body), $expected);
            backoff($attempt);
            continue;
        }

        $consecutiveBlocks = 0;
        return ['status' => $status, 'body' => (string) $body, 'error' => null];
    }

    return ['status' => 0, 'body' => '', 'error' => $lastError];
}

function looksLikeChallenge(string $body): bool
{
    foreach (['cf-browser-verification', 'Just a moment', 'Attention Required',
              'challenge-platform', '__cf_chl_'] as $needle) {
        if (stripos($body, $needle) !== false) {
            return true;
        }
    }
    return false;
}

function backoff(int $attempt): void
{
    $seconds = min(60, (2 ** $attempt)) + (mt_rand(0, 1000) / 1000);
    fwrite(STDERR, sprintf("  retrying in %.1fs...\n", $seconds));
    usleep((int) ($seconds * 1_000_000));
}

function politePause(): void
{
    global $DELAY, $JITTER;
    $seconds = $DELAY + (mt_rand(0, (int) ($JITTER * 1000)) / 1000);
    usleep((int) ($seconds * 1_000_000));
}

// ---------------------------------------------------------------------------
// URL builders and extractors
// ---------------------------------------------------------------------------

function catalogUrl(string $slug, int $page): string
{
    $base = HOST . '/auction-catalog/' . $slug;
    if ($page <= 1) {
        return $base;
    }
    // Careful: the site encodes the brackets TWICE but the "=" only once, i.e.
    //   ...prod%255Bpage%255D%3D2
    // So algoliaParam's value is the urlencoding of "prod%5Bpage%5D=2" --
    // brackets already escaped, equals sign literal. Encoding "[page]=" wholesale
    // gives %253D and the site ignores the parameter.
    $inner = ALGOLIA_INDEX . '%5Bpage%5D=' . $page;
    return $base . '?algoliaParam=' . rawurlencode($inner);
}

/** Read the highest page number linked in the pager. */
function discoverPageCount(string $html): int
{
    $max = 1;
    if (preg_match_all('/%255Bpage%255D%253D(\d+)|%255Bpage%255D%3D(\d+)/i', $html, $m)) {
        foreach (array_merge($m[1], $m[2]) as $n) {
            if ($n !== '' && (int) $n > $max) {
                $max = (int) $n;
            }
        }
    }
    // Fallback: "502 lots" at 20 per page.
    if ($max === 1 && preg_match('/([\d,]+)\s+lots/i', $html, $m)) {
        $max = (int) ceil(((int) str_replace(',', '', $m[1])) / 20);
    }
    return $max;
}

/** All /auction-lot/ URLs on a catalog page, in document order, deduped. */
function extractLotUrls(string $html): array
{
    $urls = [];
    if (preg_match_all('~/auction-lot/[A-Za-z0-9\-_]+~', $html, $m)) {
        foreach ($m[0] as $path) {
            $urls[HOST . $path] = true;
        }
    }
    return array_keys($urls);
}

/**
 * Every image.invaluable.com URL on a lot page.
 *
 * Deliberately not selector-based: the gallery is React-driven and most image
 * URLs live inside the __NEXT_DATA__ JSON blob rather than in <img> tags, with
 * JSON-escaped slashes. Scanning the unescaped raw HTML catches both.
 */
function extractImageUrls(string $html): array
{
    $unescaped = str_replace(['\\/', '\\u002F', '\\u002f'], '/', $html);
    $found = [];

    $pattern = '~https?://' . preg_quote(IMAGE_HOST, '~') . '/[^"\'\\\\\s<>)]+?\.(?:jpe?g|png|webp|gif)~i';
    if (preg_match_all($pattern, $unescaped, $m)) {
        foreach ($m[0] as $u) {
            $found[html_entity_decode($u)] = true;
        }
    }

    // Also sweep <img> attributes in case anything is served from another host.
    $dom = new DOMDocument();
    libxml_use_internal_errors(true);
    if ($dom->loadHTML('<?xml encoding="utf-8" ?>' . $html)) {
        foreach ((new DOMXPath($dom))->query('//img') as $img) {
            foreach (['src', 'data-src', 'data-original'] as $attr) {
                $v = $img->getAttribute($attr);
                if ($v && stripos($v, IMAGE_HOST) !== false) {
                    $found[$v] = true;
                }
            }
            if ($srcset = $img->getAttribute('srcset')) {
                foreach (explode(',', $srcset) as $part) {
                    $u = trim(explode(' ', trim($part))[0]);
                    if ($u && stripos($u, IMAGE_HOST) !== false) {
                        $found[$u] = true;
                    }
                }
            }
        }
    }
    libxml_clear_errors();

    return array_keys($found);
}


/**
 * Group raw image URLs into per-photo variant sets and pick the best one.
 *
 * A lot page carries more images than the lot owns:
 *   - site chrome (favicons) under /privatelabel/ -- always dropped
 *   - the prev/next browse carousel, i.e. photos of ADJACENT lots
 *   - several size variants of each real photo
 *
 * Invaluable names variants <id>_thz.JPG (thumbnail), <id>_original.JPG (full
 * size) and <id>.JPG (default). Observed rule: photos belonging to THIS lot are
 * served with an _original (and bare) variant, while carousel neighbours appear
 * as _thz only. That is the discriminator used here.
 *
 * Returns ['selected' => [base => url], 'dropped' => [base => variants],
 *          'groups' => [base => [variant => url]], 'fallback' => bool].
 */
function selectLotImages(string $html, bool $includeAll = false): array
{
    $groups = [];
    $order  = [];

    foreach (extractImageUrls($html) as $u) {
        if (stripos($u, '/housePhotos/') === false) {
            continue; // favicons and other site furniture
        }
        $file = pathinfo(parse_url($u, PHP_URL_PATH) ?: '', PATHINFO_FILENAME);
        $base = $file;
        $variant = 'default';
        if (preg_match('/^(.*)_(original|thz|thumb|small|medium|large)$/i', $file, $m)) {
            $base    = $m[1];
            $variant = strtolower($m[2]);
        }
        if (!isset($groups[$base])) {
            $groups[$base] = [];
            $order[] = $base;
        }
        $groups[$base][$variant] = $u;
    }

    $selected = [];
    $dropped  = [];
    foreach ($order as $base) {
        $v = $groups[$base];
        $ownsLot = isset($v['original']) || isset($v['default']);
        if (!$includeAll && !$ownsLot) {
            $dropped[$base] = $v;
            continue;
        }
        $selected[$base] = $v['original'] ?? $v['large'] ?? $v['default']
                        ?? $v['medium']   ?? $v['thz']   ?? reset($v);
    }

    // Never archive zero photos silently: if the heuristic rejected everything,
    // keep the lot rather than lose it, and flag that it needs a look.
    $fallback = false;
    if (!$selected && $dropped) {
        $fallback = true;
        foreach ($dropped as $base => $v) {
            $selected[$base] = $v['original'] ?? $v['default'] ?? $v['thz'] ?? reset($v);
        }
        $dropped = [];
    }

    return ['selected' => $selected, 'dropped' => $dropped,
            'groups' => $groups, 'fallback' => $fallback];
}

/**
 * Next.js App Router streams its payload as self.__next_f.push([1,"...chunk"])
 * rather than a single __NEXT_DATA__ blob. Concatenate and unescape the chunks
 * so the structured record can be archived alongside the HTML.
 */
function extractFlightData(string $html): ?string
{
    if (!preg_match_all('/self\.__next_f\.push\(\[\d+\s*,\s*"(.*?)"\]\)/s', $html, $m)) {
        return null;
    }
    $out = '';
    foreach ($m[1] as $chunk) {
        $decoded = json_decode('"' . $chunk . '"');
        $out .= is_string($decoded) ? $decoded : $chunk;
    }
    return $out !== '' ? $out : null;
}

/** Pull the Next.js Pages Router data blob, if this page still uses one. */
function extractNextData(string $html): ?array
{
    if (preg_match('~<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>~s', $html, $m)) {
        $decoded = json_decode($m[1], true);
        if (is_array($decoded)) {
            return $decoded;
        }
    }
    return null;
}

/**
 * Best-effort structured fields. Reads the rendered DOM rather than guessing at
 * the JSON schema; the full __NEXT_DATA__ blob is saved alongside so you can
 * mine anything else later without re-crawling.
 */
function extractLotMeta(string $html, string $url): array
{
    $meta = [
        'url'          => $url,
        'slug'         => basename(parse_url($url, PHP_URL_PATH) ?: ''),
        'lot_number'   => null,
        'title'        => null,
        'estimate_low' => null,
        'estimate_high'=> null,
        'current_bid'  => null,
        'bid_count'    => null,
        'description'  => null,
    ];

    $dom = new DOMDocument();
    libxml_use_internal_errors(true);
    $ok = $dom->loadHTML('<?xml encoding="utf-8" ?>' . $html);
    libxml_clear_errors();

    if ($ok) {
        $xp = new DOMXPath($dom);
        $h1 = $xp->query('//h1');
        if ($h1->length > 0) {
            $meta['title'] = normalise($h1->item(0)->textContent);
        }
        foreach (['//meta[@name="description"]/@content',
                  '//meta[@property="og:description"]/@content'] as $q) {
            $d = $xp->query($q);
            if ($d->length > 0 && trim($d->item(0)->nodeValue) !== '') {
                $meta['description'] = normalise($d->item(0)->nodeValue);
                break;
            }
        }
    }

    // App Router pages carry no meta description; mine the flight payload.
    if ($meta['description'] === null && ($flight = extractFlightData($html)) !== null) {
        if (preg_match('/"description"\s*:\s*"((?:[^"\\\\]|\\\\.){20,})"/', $flight, $m)) {
            $d = json_decode('"' . $m[1] . '"');
            if (is_string($d)) {
                $meta['description'] = normalise(strip_tags($d));
            }
        }
    }

    $text = normalise(strip_tags($html));

    if (preg_match('/\bLot\s*#?\s*([0-9]+[A-Za-z]?)\b/i', $text, $m)) {
        $meta['lot_number'] = $m[1];
    } elseif ($meta['title'] && preg_match('/^([0-9]+[A-Za-z]?):\s*/', $meta['title'], $m)) {
        $meta['lot_number'] = $m[1];
    }
    if (preg_match('/Estimate:?\s*\$?([\d,]+)\s*(?:-|–|to)\s*\$?([\d,]+)/i', $text, $m)) {
        $meta['estimate_low']  = (int) str_replace(',', '', $m[1]);
        $meta['estimate_high'] = (int) str_replace(',', '', $m[2]);
    }
    if (preg_match('/(?:Current|Starting)\s*Bid:?\s*\$?([\d,]+)/i', $text, $m)) {
        $meta['current_bid'] = (int) str_replace(',', '', $m[1]);
    }
    if (preg_match('/(\d+)\s*Bids?\b/i', $text, $m)) {
        $meta['bid_count'] = (int) $m[1];
    }

    return $meta;
}

function normalise(string $s): string
{
    return trim(preg_replace('/\s+/u', ' ', html_entity_decode($s, ENT_QUOTES | ENT_HTML5, 'UTF-8')) ?? '');
}

// ---------------------------------------------------------------------------
// Disk helpers
// ---------------------------------------------------------------------------

function ensureDir(string $path): void
{
    if (!is_dir($path) && !mkdir($path, 0775, true) && !is_dir($path)) {
        fwrite(STDERR, "Cannot create directory: $path\n");
        exit(1);
    }
}

/**
 * Write via a .part file and rename into place, so an interrupted run can never
 * leave a truncated file that the resume check mistakes for a complete one.
 */
function writeFileAtomic(string $path, string $data): bool
{
    $tmp = $path . '.part';
    if (@file_put_contents($tmp, $data) !== strlen($data)) {
        @unlink($tmp);
        return false;
    }
    if (is_file($path)) {
        @unlink($path); // rename() will not overwrite an existing file on Windows
    }
    if (!@rename($tmp, $path)) {
        @unlink($tmp);
        return false;
    }
    return true;
}

/** Remove leftovers from a previous interrupted run. */
function sweepPartFiles(string $root): int
{
    $n = 0;
    $it = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS));
    foreach ($it as $f) {
        if ($f->isFile() && str_ends_with($f->getFilename(), '.part')) {
            @unlink($f->getPathname());
            $n++;
        }
    }
    return $n;
}

function haveFile(string $path, int $minBytes = 1): bool
{
    global $FORCE;
    return !$FORCE && is_file($path) && filesize($path) >= $minBytes;
}

/** As haveFile, but also confirms the bytes decode as an image. */
function haveImage(string $path): bool
{
    global $FORCE, $flags;
    if ($FORCE || !is_file($path) || filesize($path) < 1000) {
        return false;
    }
    if ($flags['verify'] && @getimagesize($path) === false) {
        @unlink($path); // truncated or corrupt -- fetch it again
        return false;
    }
    return true;
}

function log_(string $msg): void
{
    echo $msg . "\n";
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

function cmdProbe(string $lotUrl): void
{
    log_("Probing: $lotUrl\n");
    $res = fetchUrl($lotUrl);
    if ($res['status'] !== 200) {
        log_("FAILED: HTTP {$res['status']} {$res['error']}");
        exit(1);
    }
    $html = $res['body'];
    log_(sprintf("HTTP 200, %s bytes\n", number_format(strlen($html))));

    $meta = extractLotMeta($html, $lotUrl);
    log_("--- Extracted fields ---");
    foreach ($meta as $k => $v) {
        log_(sprintf('  %-14s %s', $k . ':', $v === null ? '(not found)' : mb_strimwidth((string) $v, 0, 90, '...')));
    }

    $next = extractNextData($html);
    log_("\n--- __NEXT_DATA__ ---");
    log_($next === null
        ? '  not found (extractor will fall back to HTML only)'
        : '  present, ' . count($next, COUNT_RECURSIVE) . ' nodes -- will be saved as next-data.json');

    global $flags;
    $sel = selectLotImages($html, $flags['include-all-images']);

    log_("\n--- Images ---");
    log_(sprintf('  %d raw URLs -> %d photos for this lot, %d discarded',
        count($sel['groups']) + 0, count($sel['selected']), count($sel['dropped'])));
    if ($sel['fallback']) {
        log_('  WARNING: variant heuristic matched nothing; kept everything as a fallback.');
    }
    foreach ($sel['selected'] as $base => $url) {
        log_(sprintf('  KEEP  %s  [%s]', $base, implode(', ', array_keys($sel['groups'][$base]))));
        log_('        ' . $url);
    }
    foreach ($sel['dropped'] as $base => $variants) {
        log_(sprintf('  DROP  %s  [%s]  (adjacent lot or site chrome)',
            $base, implode(', ', array_keys($variants))));
    }

    $images = array_values($sel['selected']);

    // Measure a photo we will actually download, not whatever appeared first.
    if ($images) {
        politePause();
        $img = fetchUrl($images[0], true);
        if ($img['status'] === 200) {
            $tmp = tempnam(sys_get_temp_dir(), 'probe');
            file_put_contents($tmp, $img['body']);
            $size = @getimagesize($tmp);
            log_(sprintf("\nFirst selected photo: %s bytes, %s",
                number_format(strlen($img['body'])),
                $size ? "{$size[0]}x{$size[1]}px" : 'dimensions unreadable'));
            log_($size && $size[0] >= 800
                ? '  ^ full resolution, good.'
                : '  ^ smaller than expected -- compare against the browser before crawling.');
            @unlink($tmp);
        }
    }

    log_("\nIf the fields and image count match what you see in the browser, run the full crawl.");
}

function cmdRun(array $days): void
{
    global $OUT, $LIMIT, $flags;

    ensureDir($OUT);

    if (($swept = sweepPartFiles($OUT)) > 0) {
        log_("Cleaned $swept incomplete file(s) from a previous interrupted run.");
    }

    foreach ($days as $day) {
        if (!isset(CATALOGS[$day])) {
            log_("Unknown day '$day', skipping.");
            continue;
        }
        $slug  = CATALOGS[$day]['slug'];
        $label = CATALOGS[$day]['label'];
        $root  = "$OUT/$label";
        ensureDir("$root/catalog");
        ensureDir("$root/lots");

        log_("\n=== $label ($slug) ===");

        // --- Phase 1: catalog pages -----------------------------------------
        $firstPath = "$root/catalog/page-001.html";
        if (haveFile($firstPath, MIN_HTML_BYTES)) {
            $firstHtml = (string) file_get_contents($firstPath);
            log_('  page 1 (cached)');
        } else {
            $res = fetchUrl(catalogUrl($slug, 1));
            if ($res['status'] !== 200) {
                log_("  page 1 FAILED: HTTP {$res['status']} {$res['error']}");
                continue;
            }
            $firstHtml = $res['body'];
            writeFileAtomic($firstPath, $firstHtml);
            log_('  page 1 ok');
            politePause();
        }

        $pageCount = discoverPageCount($firstHtml);
        log_("  $pageCount catalog pages");

        $lotUrls = extractLotUrls($firstHtml);

        for ($p = 2; $p <= $pageCount; $p++) {
            $path = sprintf('%s/catalog/page-%03d.html', $root, $p);
            if (haveFile($path, MIN_HTML_BYTES)) {
                $html = (string) file_get_contents($path);
                log_("  page $p (cached)");
            } else {
                $res = fetchUrl(catalogUrl($slug, $p));
                if ($res['status'] !== 200) {
                    log_("  page $p FAILED: HTTP {$res['status']} {$res['error']}");
                    politePause();
                    continue;
                }
                $html = $res['body'];
                writeFileAtomic($path, $html);
                log_("  page $p ok");
                politePause();
            }
            $lotUrls = array_merge($lotUrls, extractLotUrls($html));
        }

        $lotUrls = array_values(array_unique($lotUrls));
        writeFileAtomic("$root/lot-urls.txt", implode("\n", $lotUrls) . "\n");
        log_('  ' . count($lotUrls) . ' unique lot URLs');

        if ($flags['no-lots']) {
            continue;
        }

        // --- Phase 2 + 3: lot pages and images ------------------------------
        $n = 0;
        foreach ($lotUrls as $lotUrl) {
            $n++;
            if ($LIMIT > 0 && $n > $LIMIT) {
                log_("  --limit reached, stopping this day");
                break;
            }

            $lotSlug = basename(parse_url($lotUrl, PHP_URL_PATH) ?: "lot-$n");
            $lotDir  = "$root/lots/$lotSlug";
            $htmlPath = "$lotDir/lot.html";
            ensureDir($lotDir);

            if (haveFile($htmlPath, MIN_HTML_BYTES)) {
                $html = (string) file_get_contents($htmlPath);
            } else {
                $res = fetchUrl($lotUrl);
                if ($res['status'] !== 200) {
                    log_(sprintf('  [%d/%d] %s FAILED HTTP %d', $n, count($lotUrls), $lotSlug, $res['status']));
                    file_put_contents("$root/failed-lots.txt", $lotUrl . "\n", FILE_APPEND);
                    politePause();
                    continue;
                }
                $html = $res['body'];
                writeFileAtomic($htmlPath, $html);
                politePause();
            }

            $meta = extractLotMeta($html, $lotUrl);
            if ($next = extractNextData($html)) {
                writeFileAtomic("$lotDir/next-data.json",
                    json_encode($next, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));
            } elseif (($flight = extractFlightData($html)) !== null) {
                writeFileAtomic("$lotDir/flight-data.txt", $flight);
            }

            $sel = selectLotImages($html, $flags['include-all-images']);
            $images = array_values($sel['selected']);
            $meta['image_count']    = count($images);
            $meta['images']         = $images;
            $meta['image_variants'] = $sel['groups'];
            if ($sel['fallback']) {
                $meta['image_warning'] = 'variant heuristic matched nothing; kept all';
                file_put_contents("$root/review-images.txt", $lotUrl . "\n", FILE_APPEND);
            }

            if (!$flags['no-images'] && $images) {
                ensureDir("$lotDir/images");
                foreach ($images as $i => $imgUrl) {
                    $ext = strtolower(pathinfo(parse_url($imgUrl, PHP_URL_PATH) ?: '', PATHINFO_EXTENSION) ?: 'jpg');
                    $imgPath = sprintf('%s/images/%03d.%s', $lotDir, $i + 1, $ext);
                    if (haveImage($imgPath)) {
                        continue;
                    }
                    $img = fetchUrl($imgUrl, true);
                    if ($img['status'] === 200 && strlen($img['body']) > 1000) {
                        writeFileAtomic($imgPath, $img['body']);
                    } else {
                        file_put_contents("$root/failed-images.txt", $imgUrl . "\n", FILE_APPEND);
                    }
                    politePause();
                }
            }

            writeFileAtomic("$lotDir/meta.json",
                json_encode($meta, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

            log_(sprintf('  [%d/%d] %s  %s  (%d img)',
                $n, count($lotUrls),
                str_pad((string) ($meta['lot_number'] ?? '?'), 6),
                mb_strimwidth((string) ($meta['title'] ?? $lotSlug), 0, 60, '...'),
                count($images)));
        }
    }

    log_("\nDone. Building CSV...");
    cmdReport(array_map(fn($d) => CATALOGS[$d]['label'] ?? $d, $days));
}

/** Report how far the crawl has got, without touching the network. */
function cmdStatus(array $days): void
{
    global $OUT;

    if (!is_dir($OUT)) {
        log_("No output directory at $OUT -- nothing crawled yet.");
        return;
    }

    $totLots = $totImgs = $totBytes = 0;

    foreach ($days as $day) {
        if (!isset(CATALOGS[$day])) {
            continue;
        }
        $label = CATALOGS[$day]['label'];
        $root  = "$OUT/$label";
        if (!is_dir($root)) {
            log_(sprintf('%-6s not started', $label));
            continue;
        }

        $pages    = count(glob("$root/catalog/page-*.html") ?: []);
        $expected = 0;
        $first    = "$root/catalog/page-001.html";
        if (is_file($first)) {
            $expected = discoverPageCount((string) file_get_contents($first));
        }

        $known = is_file("$root/lot-urls.txt")
            ? count(array_filter(file("$root/lot-urls.txt", FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES)))
            : 0;

        $done = count(glob("$root/lots/*/meta.json") ?: []);

        // Exclude .part leftovers so the count reflects completed downloads only.
        $imageFiles = array_filter(glob("$root/lots/*/images/*") ?: [],
            fn(string $f): bool => !str_ends_with($f, '.part'));
        $imgs = count($imageFiles);

        $bytes = 0;
        foreach ($imageFiles as $f) {
            $bytes += filesize($f) ?: 0;
        }

        $noImages = 0;
        foreach ((glob("$root/lots/*/meta.json") ?: []) as $f) {
            $m = json_decode((string) file_get_contents($f), true);
            if (is_array($m) && (int) ($m['image_count'] ?? 0) === 0) {
                $noImages++;
            }
        }

        $failed = countUniqueLines("$root/failed-lots.txt");
        $review = countUniqueLines("$root/review-images.txt");
        $parts  = count(glob("$root/lots/*/*.part") ?: []) + count(glob("$root/lots/*/images/*.part") ?: []);

        log_(sprintf('%-6s catalog %d/%s pages | lots %d/%d (%s) | %d images, %s',
            $label,
            $pages, $expected ?: '?',
            $done, $known,
            $known > 0 ? round($done / $known * 100) . '%' : '0%',
            $imgs, humanBytes($bytes)));

        foreach ([['failed lots', $failed], ['lots flagged for image review', $review],
                  ['lots with zero images', $noImages], ['stray .part files', $parts]] as [$what, $n]) {
            if ($n > 0) {
                log_(sprintf('       %d %s', $n, $what));
            }
        }

        $totLots  += $done;
        $totImgs  += $imgs;
        $totBytes += $bytes;
    }

    log_(sprintf("\nTotal: %d lots, %d images, %s on disk", $totLots, $totImgs, humanBytes($totBytes)));
    log_('Re-run the same "run" command to continue; anything already saved is skipped.');
}

function countUniqueLines(string $path): int
{
    if (!is_file($path)) {
        return 0;
    }
    $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [];
    return count(array_unique($lines));
}

function humanBytes(int $b): string
{
    foreach (['B', 'KB', 'MB', 'GB'] as $unit) {
        if ($b < 1024 || $unit === 'GB') {
            return round($b, 1) . $unit;
        }
        $b = intdiv($b, 1024);
    }
    return $b . 'B';
}

function cmdReport(array $labels): void
{
    global $OUT;

    $csvPath = "$OUT/lots.csv";
    $fh = fopen($csvPath, 'w');
    fputcsv($fh, ['day', 'lot_number', 'title', 'estimate_low', 'estimate_high',
                  'current_bid', 'bid_count', 'image_count', 'url']);

    $rows = 0;
    foreach ($labels as $label) {
        $dir = "$OUT/$label/lots";
        if (!is_dir($dir)) {
            continue;
        }
        foreach (glob("$dir/*/meta.json") ?: [] as $file) {
            $m = json_decode((string) file_get_contents($file), true);
            if (!is_array($m)) {
                continue;
            }
            fputcsv($fh, [
                $label,
                $m['lot_number'] ?? '',
                $m['title'] ?? '',
                $m['estimate_low'] ?? '',
                $m['estimate_high'] ?? '',
                $m['current_bid'] ?? '',
                $m['bid_count'] ?? '',
                $m['image_count'] ?? 0,
                $m['url'] ?? '',
            ]);
            $rows++;
        }
    }
    fclose($fh);
    log_("Wrote $rows rows to $csvPath");
}

// ---------------------------------------------------------------------------
// Dispatch
// ---------------------------------------------------------------------------

$days = array_values(array_filter(array_map('trim', explode(',', $opt['days']))));

if ($CAINFO !== '') {
    fwrite(STDERR, 'TLS: using CA bundle ' . $CAINFO . "\n");
} elseif (ini_get('curl.cainfo') === '' && stripos(PHP_OS_FAMILY, 'Windows') !== false) {
    fwrite(STDERR, "TLS: no CA bundle found. If you hit a certificate error, drop\n"
        . "     cacert.pem (https://curl.se/ca/cacert.pem) next to this script.\n");
}

switch ($command) {
    case 'probe':
        if (!isset($positional[0])) {
            fwrite(STDERR, "Usage: php thomaston-scrape.php probe <lot-url>\n");
            exit(1);
        }
        cmdProbe($positional[0]);
        break;

    case 'run':
        cmdRun($days);
        break;

    case 'status':
        cmdStatus($days);
        break;

    case 'report':
        cmdReport(array_map(fn($d) => CATALOGS[$d]['label'] ?? $d, $days));
        break;

    default:
        echo file_get_contents(__FILE__, false, null, 0, 2100);
        break;
}