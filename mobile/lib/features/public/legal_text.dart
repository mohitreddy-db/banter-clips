/// The Privacy Policy and Terms of Service, word for word from
/// `frontend/src/pages/Legal.jsx` on banterclips.com. Both stores require
/// these to be reachable from inside the app; keeping the text here (rather
/// than a webview) means they read fine offline and in the app's own type.
///
/// When the website's copy changes, change it here in the same commit —
/// the effective date below is the one the site shows.
library;

const legalEffectiveDate = 'September 12, 2026';
const legalSupportEmail = 'support@banterclips.com';

/// A section is a heading plus a list of blocks; a block is either a
/// paragraph (`p`) or a bulleted item (`li`). A bullet may start with a
/// bold lead-in, written `**Lead.** rest of the sentence`.
class LegalSection {
  const LegalSection(this.heading, this.blocks);
  final String heading;
  final List<LegalBlock> blocks;
}

class LegalBlock {
  const LegalBlock.p(this.text) : bullet = false;
  const LegalBlock.li(this.text) : bullet = true;
  final String text;
  final bool bullet;
}

const privacyPolicy = <LegalSection>[
  LegalSection('', [
    LegalBlock.p(
      'BanterClips (“we”, “us”) is an app that turns a written sports opinion into a short AI-generated parody video you can publish to your own social accounts. This policy explains what we collect, why, and what happens to it. The short version: we collect what the product needs to work, we never sell your data, and you can delete everything.',
    ),
  ]),
  LegalSection('What we collect', [
    LegalBlock.li(
      '**Account details.** Your email address, display name, and a password (stored only as a secure hash by our authentication provider). If you sign in with Google, we receive your name, email address and basic profile from Google for authentication. Connecting YouTube is a separate, optional authorization described below.',
    ),
    LegalBlock.li(
      '**Preferences.** Optional onboarding choices: favourite sports, teams, players, and your creator role. All skippable, editable, and used only to pre-fill defaults.',
    ),
    LegalBlock.li(
      '**Your content.** The takes you write, the videos and thumbnails we generate from them, the captions you write, and your publish history. Your videos remain private unless you explicitly publish them to a connected social account.',
    ),
    LegalBlock.li(
      '**Social connections.** If you explicitly connect Instagram, TikTok or YouTube, we store the connection record and OAuth tokens needed to publish. For YouTube this includes a server-side access token, refresh token, token expiry and a connection identifier for the youtube.upload permission. We do not read your existing YouTube videos, channel library, subscribers, comments, analytics or viewer data, and nothing is ever posted automatically.',
    ),
    LegalBlock.li(
      '**YouTube API Services and API Data.** YouTube publishing uses YouTube API Services. By connecting a YouTube channel you agree to the YouTube Terms of Service (youtube.com/t/terms), and Google’s handling of your data is described in the Google Privacy Policy (policies.google.com/privacy). In addition to the authorization data above, a successful upload returns a YouTube video ID. We temporarily store that ID in the Shorts link shown in your BanterClips publish history, together with our own upload status and timestamp. We delete the API-returned ID/link within 30 days because our upload-only permission cannot refresh it. We do not download or store the uploaded video back from YouTube.',
    ),
    LegalBlock.li(
      '**Payment details.** Web payments run through Stripe; purchases made inside the app run through Apple or Google. Your card number never touches our servers; we store only the provider’s customer, subscription or purchase identifiers and your plan status.',
    ),
    LegalBlock.li(
      '**Usage data.** Product events (sign-up, generation started or finished, publish, upgrade) and standard server logs, used to run and improve the product. We use no third-party advertising or cross-site trackers and show no ads.',
    ),
  ]),
  LegalSection('Storage and device information', [
    LegalBlock.p(
      'BanterClips stores and accesses information on your device using the strictly necessary technologies below. We do not use advertising identifiers, cross-site tracking, fingerprinting, or similar technology to build advertising profiles.',
    ),
    LegalBlock.li(
      '**Secure storage for sign-in.** The app keeps a BanterClips session token and, when Supabase authentication is enabled, Supabase authentication session data needed to keep you signed in and refresh that session — in the device keychain or keystore. It remains until you sign out or the session expires.',
    ),
    LegalBlock.li(
      '**Cached feeds for performance.** The trending-sports feed is cached briefly so navigating back does not repeat the same request. It contains no YouTube API Data.',
    ),
    LegalBlock.li(
      '**Necessary request and security data.** Our hosting, authentication and infrastructure providers (Vercel, DigitalOcean, Cloudflare and Supabase) receive ordinary request information such as IP address, device/user-agent, timestamps and security headers when your device connects. These providers process essential routing, security or session signals solely to deliver and protect the service.',
    ),
    LegalBlock.p(
      'You can remove this local information through Sign out or by uninstalling the app.',
    ),
  ]),
  LegalSection('How we use it', [
    LegalBlock.li(
      'To provide the service: generate your videos, show your library, publish on your explicit instruction, enforce plan limits, and bill your subscription.',
    ),
    LegalBlock.li(
      'To generate a video, your take and creative choices are sent to the AI model providers listed below. They are used to produce your video, not to build advertising profiles.',
    ),
    LegalBlock.li(
      'To send account emails (verification, password reset). No marketing emails without a separate opt-in.',
    ),
    LegalBlock.li(
      'To keep the service safe: content checks against hate, threats and harassment, and abuse prevention.',
    ),
  ]),
  LegalSection('Who processes it for us', [
    LegalBlock.p(
      'We share data only with the service providers that run the product, each bound to use it solely to provide their service to us:',
    ),
    LegalBlock.li(
      '**Supabase** — authentication, database and video storage (hosted in the AWS Asia-Pacific region).',
    ),
    LegalBlock.li(
      '**Vercel** — web hosting. **DigitalOcean** — application servers. **Cloudflare** — DNS.',
    ),
    LegalBlock.li(
      '**Stripe, Apple and Google** — payments and subscriptions.',
    ),
    LegalBlock.li(
      '**OpenAI** and **OpenRouter / xAI** — AI models that write the script and generate the video from your take.',
    ),
    LegalBlock.li(
      '**Meta (Instagram)**, **TikTok** and **Google/YouTube** — receive the video and caption, title or description you selected only when you press Publish for that platform.',
    ),
    LegalBlock.li('**Resend** — delivers account emails.'),
    LegalBlock.p(
      'We do not sell personal data, and we do not share it with data brokers or advertisers.',
    ),
  ]),
  LegalSection('Google user data', [
    LegalBlock.li(
      '**Google sign-in.** We use your basic profile (name, email and picture) solely to create and authenticate your BanterClips account.',
    ),
    LegalBlock.li(
      '**YouTube publishing.** If you separately connect YouTube, we request only https://www.googleapis.com/auth/youtube.upload. Before every upload, you set and review the title, description and visibility (Public, Unlisted or Private). We send those exact values with the completed video only after you explicitly press Upload to YouTube. We do not read your existing videos, upload in the background, or take actions unrelated to that upload.',
    ),
    LegalBlock.li(
      '**Storage and sharing.** OAuth access and refresh tokens are kept server-side while the connection is active and are never exposed to the app. The selected video and metadata are sent to Google/YouTube only to complete your requested upload. We retain the returned video ID/link for no more than 30 days as described above; we do not share YouTube API Data with any other third party.',
    ),
    LegalBlock.li(
      '**Limited use.** Google user data is never sold, used for advertising, or used to train AI models. Our use of information from Google APIs follows the Google API Services User Data Policy, including its Limited Use requirements.',
    ),
  ]),
  LegalSection('Retention and deletion', [
    LegalBlock.li(
      'Your content is kept while your account is active, until you delete the clip or request account deletion. Deleting a clip removes its video files, not just the listing.',
    ),
    LegalBlock.li(
      'YouTube access tokens are refreshed when they are close to expiring: before an upload, when connected accounts load, and by hourly housekeeping. This also detects grants revoked from Google settings. Authorization tokens are retained only while your connection is active.',
    ),
    LegalBlock.li(
      'A YouTube video ID/link returned by videos.insert is deleted after no more than 30 days because we do not request the read permission needed to refresh it. Our own upload status, timestamp and the title, description and visibility you entered remain with the clip until you delete that clip or your account.',
    ),
    LegalBlock.li(
      'Disconnecting YouTube immediately asks Google to revoke the grant and deletes our stored access token, refresh token, expiry, connection identifier and every retained YouTube video ID/link. You can also revoke access from Google Security settings; our scheduled check detects that change and removes the same data.',
    ),
    LegalBlock.li(
      'You can delete your account — including your videos, preferences, social connections and billing identifiers — from Account → “Delete my account and videos” in the app, which removes it immediately, or by emailing $legalSupportEmail. YouTube API Data and authorization tokens are deleted as soon as possible and within seven calendar days; remaining account deletion completes within 30 days. Step-by-step instructions: banterclips.com/data-deletion.',
    ),
  ]),
  LegalSection('Your rights', [
    LegalBlock.p(
      'You can access and correct your details from your account page, and request a copy or deletion of your data by email. Depending on where you live (e.g. the EU/UK under GDPR, or India under the DPDP Act), you may have additional statutory rights; we honour requests from all users the same way.',
    ),
  ]),
  LegalSection('Security', [
    LegalBlock.p(
      'All traffic is encrypted in transit (TLS). Passwords are hashed, and social tokens are stored server-side and never exposed to the app. Publishing and payment are always explicit user actions.',
    ),
  ]),
  LegalSection('Children', [
    LegalBlock.p(
      'BanterClips is not directed at children under 13, and we do not knowingly collect their data.',
    ),
  ]),
  LegalSection('Changes', [
    LegalBlock.p(
      'If this policy changes materially, we will update the date above and note the change in the product. Continued use after a change means acceptance.',
    ),
  ]),
];

const termsOfService = <LegalSection>[
  LegalSection('', [
    LegalBlock.p(
      'These terms govern your use of BanterClips. By creating an account you agree to them. BanterClips is currently in beta: things will change, and occasionally break.',
    ),
  ]),
  LegalSection('The service', [
    LegalBlock.p(
      'You write a sports take; we generate a short, clearly-labelled AI-parody video from it, which you can preview and — at your explicit instruction — publish to a social account you connect, or download on a paid plan.',
    ),
  ]),
  LegalSection('Your content', [
    LegalBlock.li(
      'Your takes are yours. You grant us the licence needed to process them (including via the AI providers named in the Privacy Policy) solely to provide the service.',
    ),
    LegalBlock.li(
      'You may use and publish the videos generated for you. The BanterClips watermark is removed only on the paid plan. Present generated videos as AI-generated content wherever the platform you publish to requires it.',
    ),
    LegalBlock.li(
      'Your videos stay private to your account unless you publish them.',
    ),
  ]),
  LegalSection('AI-generated parody', [
    LegalBlock.p(
      'Videos are entirely AI-generated satire and parody. They may depict real athletes and kits in fictional, comedic scenarios; they contain no real match footage or broadcast material, and they do not represent real events, statements, or endorsements. BanterClips is not affiliated with, sponsored by, or endorsed by any league, club, or athlete.',
    ),
  ]),
  LegalSection('Acceptable use', [
    LegalBlock.li(
      'Playful rivalry is the point; hate speech, threats, harassment, and attacks on protected characteristics are not allowed and are blocked or removed.',
    ),
    LegalBlock.li(
      'Do not present generated content as real news, real quotes, or real events, and do not use the service to defame or deceive.',
    ),
    LegalBlock.li(
      'You are responsible for what you choose to publish to your own social accounts, and for complying with those platforms’ rules. Connecting a YouTube channel also means you agree to the YouTube Terms of Service.',
    ),
    LegalBlock.li(
      'No attempts to break, overload, or reverse-engineer the service.',
    ),
  ]),
  LegalSection('Plans and billing', [
    LegalBlock.li(
      'Free: one-time welcome credits on signup, published with a watermark, 720p, up to 15 seconds. Creator (\$19/month): 150 credits monthly, 1080p available, up to 30 seconds, watermark-free downloads. Credit top-up packs are available to both plans and never expire.',
    ),
    LegalBlock.li(
      'Credits are charged only when a video completes — failures, abandoned scripts and retries release the reservation in full.',
    ),
    LegalBlock.li(
      'Web billing runs through Stripe; eligible iOS and Android app purchases run through Apple or Google. Upgrades apply after provider verification, and cancellation applies at the end of the paid period. Store subscriptions are managed in the applicable store. Your videos are never deleted for billing reasons.',
    ),
  ]),
  LegalSection('Availability and liability', [
    LegalBlock.p(
      'The service is provided “as is”, without warranties, during beta. To the maximum extent permitted by law, our total liability for any claim is limited to the amount you paid us in the three months before the claim. Nothing in these terms limits liability that cannot lawfully be limited.',
    ),
  ]),
  LegalSection('Termination', [
    LegalBlock.p(
      'You can delete your account at any time (see the Privacy Policy). We may suspend accounts that violate these terms, with notice where practical.',
    ),
  ]),
  LegalSection('Changes', [
    LegalBlock.p(
      'We may update these terms as the product evolves; material changes will be noted in the product. Continued use after a change means acceptance.',
    ),
  ]),
];
