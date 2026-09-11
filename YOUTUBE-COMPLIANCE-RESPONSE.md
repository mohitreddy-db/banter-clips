# YouTube API Services compliance response

**API Client:** BanterClips, operated by Multiple Codes LLC  
**Google Cloud project:** `banter-clips`  
**Project number:** `49190798823`  
**Canonical product:** https://www.banterclips.com  
**Privacy Policy:** https://www.banterclips.com/privacy  
**Terms of Service:** https://www.banterclips.com/terms  
**Data deletion:** https://www.banterclips.com/data-deletion

## Reply draft

Hello,

Thank you for the detailed report. We resolved every item listed in the September 10, 2026 ToS Violations Report V.1 for BanterClips. The resolutions are below.

### III.D.1.c — API project confirmation

BanterClips uses exactly one Google Cloud project for this API Client: project number **49190798823** (`banter-clips`). We do not split, shard, or rotate YouTube API traffic across multiple projects. The OAuth credentials used for BanterClips sign-in and its optional YouTube upload feature belong to that same project. No other project number is used by this API Client.

### III.A.2.g — cookies and similar technologies

We expanded the public Privacy Policy with a dedicated **“Cookies, browser storage and device information”** section. It now clearly discloses:

- browser local storage used for the BanterClips and Supabase authentication sessions;
- session storage used to cache the trending-sports feed for up to 20 minutes;
- ordinary device/request information processed by our infrastructure providers; and
- Cloudflare’s possible use of the short-lived, strictly necessary `__cf_bm` bot-management cookie on the authentication domain.

The policy also states that BanterClips does not use advertising cookies, cross-site tracking pixels, fingerprinting, or similar technology to create advertising profiles, and explains how users can remove local site data.

### III.C.1 / Required Minimum Functionality — video upload properties

The YouTube upload composer now requires the creator to review and set all three required properties for every upload:

1. **Title** — editable up to YouTube’s full 100-character limit;
2. **Description** — editable up to 5000 UTF-8 bytes; and
3. **Visibility** — an explicit choice of **Public, Unlisted, or Private**, with no preselected visibility.

The upload action remains disabled until all required choices are valid. The composer shows the destination, exact metadata, selected visibility, and synthetic-media disclosure immediately before the distinct **Upload to YouTube** action. The backend validates the same limits and sends the creator’s values unchanged to `videos.insert`; there is no global/default privacy setting and no hidden caption-to-title conversion.

### III.E.4.a–g — refresh, update, and deletion frequency

BanterClips requests only `youtube.upload` and does not retrieve existing videos, channel libraries, comments, subscribers, viewer data, or analytics.

The lifecycle is now:

- **OAuth access token:** refreshed close to expiry (normally about hourly), before an upload, when the connected-accounts view loads, and by hourly scheduled housekeeping.
- **Revocation made in Google Security settings:** the scheduled validation detects `invalid_grant`, marks the connection revoked, and immediately deletes locally stored YouTube credentials and API-returned data.
- **`videos.insert` response:** the returned video ID is temporarily retained only in the Shorts link shown in the user’s publish history. Because the upload-only scope cannot refresh that value, it is automatically deleted no later than **30 calendar days** after upload.
- **Disconnect in BanterClips:** immediately calls Google’s revocation endpoint and deletes the stored access token, refresh token, expiry, connection identifier, and every retained YouTube video ID/link. Videos already stored by YouTube are not deleted by disconnect.
- **Clip deletion:** deletes the clip’s local publish history and stored media immediately.
- **Account-deletion request:** YouTube authorization tokens and API Data are deleted as soon as possible and within **seven calendar days**; remaining account data is deleted within 30 days.

These schedules and deletion effects are stated in both the Privacy Policy and the public data-deletion page.

### III.F.2.a — YouTube branding

We removed the hand-drawn YouTube mark and replaced it with the unmodified official **Core YouTube Icon** downloaded from https://brand.youtube/youtube-icon. The icon’s aspect ratio, colors, and clear space are preserved on a solid contrasting background.

Every YouTube mark is now rendered at a minimum of **24 CSS pixels** (above the requested 20dp minimum). YouTube marks link either to the relevant YouTube video/YouTube itself or sit inside the clickable control that opens the YouTube-specific component.

### Additional preventive corrections

We also made the following changes to prevent related review issues:

- The onboarding connect surface now shows “Uses YouTube API Services,” the YouTube Terms of Service, and the Google Privacy Policy before connection.
- YouTube OAuth no longer combines earlier Google grants (`include_granted_scopes` was removed), and the callback rejects any unexpected returned scope.
- OAuth returns users to the exact clip and reopens the YouTube upload composer instead of losing the publish flow.
- A missing production OAuth configuration can no longer create a connected-looking mock account.
- Disconnect now includes a clear confirmation explaining revocation, local deletion, and that already-uploaded YouTube videos remain on YouTube.
- The support/admin account-erasure path revokes connected platform grants before deleting rows and also removes the external Supabase authentication identity.
- An admin cannot initiate a YouTube retry; every YouTube upload or retry requires a new explicit action by the authenticated creator.
- OAuth callback query strings are excluded from server access logs so authorization codes and state are not stored in journald.
- Privacy, Terms, and data-deletion links remain accessible from the authenticated product.
- Every upload still sends `containsSyntheticMedia: true`. We removed the guessed made-for-kids value so YouTube applies the channel’s own audience setting.

Please find attached a new screencast showing the complete corrected flow and end result, plus screenshots of the revised Privacy Policy, all three YouTube metadata/visibility controls, the official branding at compliant size, and the resulting video in YouTube Studio.

Regards,  
Mohit Reddy  
Multiple Codes LLC  
https://www.banterclips.com

## Evidence checklist before sending

Record one uninterrupted production screencast that shows:

1. the browser address bar on `https://www.banterclips.com`;
2. Privacy Policy → “Cookies, browser storage and device information” and YouTube API Data/retention sections;
3. Account → YouTube disclosure links and official icon;
4. Connect → Google consent showing only `youtube.upload`;
5. return to the same finished clip with the YouTube composer reopened;
6. edit the Title and Description;
7. show that no visibility is preselected, then select Public, Unlisted, and Private in turn before choosing the intended value;
8. press the single, explicit **Upload to YouTube** button once;
9. show the successful publish status, selected visibility, and YouTube link; and
10. show the resulting video and matching title/description/visibility in YouTube Studio.

Attach still screenshots of:

- all three metadata/visibility controls in one frame;
- the Privacy Policy browser-storage section;
- the Privacy Policy YouTube retention/deletion section;
- the Account YouTube row with official branding and legal links;
- the resulting YouTube Studio video details; and
- Google Cloud Console’s project selector/credentials or quota page showing project number `49190798823` (do not expose client secrets or tokens).

Before sending, inventory Google Cloud Console once more for any old project that ever carried BanterClips YouTube API traffic. If one exists, disclose its project number and stop using it; do not omit it from the answer.
