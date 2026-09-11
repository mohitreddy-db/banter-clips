import { Link } from "react-router-dom";
import { useSeo } from "../lib/seo.js";

/**
 * Privacy policy and terms of service.
 *
 * These exist because Google OAuth verification requires a privacy policy
 * URL and Meta App Review requires both. Written to describe what the
 * product actually does — every claim here should stay true of the code, so
 * when behaviour changes (new subprocessor, new data collected), change this
 * page in the same PR.
 */

const EFFECTIVE = "September 12, 2026";
const CONTACT = "support@banterclips.com";

function Layout({ title, children }) {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--text)" }}>
      <div style={{ maxWidth: 760, margin: "0 auto", padding: "clamp(28px, 6vw, 48px) clamp(18px, 5vw, 24px) 80px" }}>
        <Link to="/" style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "var(--muted)", fontSize: 14, textDecoration: "none", marginBottom: 28 }}>
          ← BanterClips
        </Link>
        <h1 style={{ fontFamily: "var(--display)", fontSize: "clamp(26px, 6.5vw, 34px)", fontWeight: 800, margin: "0 0 6px" }}>{title}</h1>
        <div style={{ color: "var(--muted2)", fontSize: 13.5, marginBottom: 34 }}>Effective {EFFECTIVE}</div>
        <div className="legal-body" style={{ fontSize: 15, lineHeight: 1.7, color: "var(--muted)" }}>
          {children}
        </div>
        <div style={{ marginTop: 48, paddingTop: 20, borderTop: "1px solid var(--border)", fontSize: 13.5, color: "var(--muted2)" }}>
          Questions? Email <a href={`mailto:${CONTACT}`} style={{ color: "var(--muted)" }}>{CONTACT}</a>
          {" · "}
          <Link to="/privacy" style={{ color: "var(--muted)" }}>Privacy</Link>
          {" · "}
          <Link to="/terms" style={{ color: "var(--muted)" }}>Terms</Link>
          {" · "}
          <Link to="/data-deletion" style={{ color: "var(--muted)" }}>Data deletion</Link>
        </div>
      </div>
    </div>
  );
}

const H = ({ children }) => (
  <h2 style={{ fontSize: 19, fontWeight: 700, color: "var(--text)", margin: "34px 0 10px" }}>{children}</h2>
);
const P = ({ children }) => <p style={{ margin: "0 0 12px" }}>{children}</p>;
const LI = ({ children }) => <li style={{ margin: "0 0 8px" }}>{children}</li>;
const UL = ({ children }) => <ul style={{ margin: "0 0 12px", paddingLeft: 22 }}>{children}</ul>;
const B = ({ children }) => <b style={{ color: "var(--text)", fontWeight: 600 }}>{children}</b>;

export function Privacy() {
  useSeo({
    title: "Privacy Policy — BanterClips",
    description:
      "How BanterClips collects, uses and stores your data — what we keep, which subprocessors we use, and how to delete your account.",
    path: "/privacy",
  });

  return (
    <Layout title="Privacy Policy">
      <P>
        BanterClips (&ldquo;we&rdquo;, &ldquo;us&rdquo;) is a web app that turns a written sports
        opinion into a short AI-generated parody video you can publish to your
        own social accounts. This policy explains what we collect, why, and
        what happens to it. The short version: we collect what the product
        needs to work, we never sell your data, and you can delete everything.
      </P>

      <H>What we collect</H>
      <UL>
        <LI><B>Account details.</B> Your email address, display name, and a
          password (stored only as a secure hash by our authentication
          provider). If you sign in with Google, we receive your name, email
          address and basic profile from Google for authentication. Connecting
          YouTube is a separate, optional authorization described below.</LI>
        <LI><B>Preferences.</B> Optional onboarding choices: favourite sports,
          teams, players, and your creator role. All skippable, editable, and
          used only to pre-fill defaults.</LI>
        <LI><B>Your content.</B> The takes you write, the videos and thumbnails
          we generate from them, the captions you write, and your publish
          history. Your videos remain private unless you explicitly publish
          them to a connected social account.</LI>
        <LI><B>Social connections.</B> If you explicitly connect Instagram,
          TikTok or YouTube, we store the connection record and OAuth tokens
          needed to publish. For YouTube this includes a server-side access
          token, refresh token, token expiry and a connection identifier for the
          <code>youtube.upload</code> permission. We do not read your existing
          YouTube videos, channel library, subscribers, comments, analytics or
          viewer data, and nothing is ever posted automatically.</LI>
        <LI><B>YouTube API Services and API Data.</B> YouTube publishing uses
          YouTube API Services. By connecting a YouTube channel you agree to the
          <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer" style={{ color: "var(--cyan)" }}> YouTube Terms of Service</a>,
          and Google&rsquo;s handling of your data is described in the
          <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer" style={{ color: "var(--cyan)" }}> Google Privacy Policy</a>.
          In addition to the authorization data above, a successful upload
          returns a YouTube video ID. We temporarily store that ID in the Shorts
          link shown in your BanterClips publish history, together with our own
          upload status and timestamp. We delete the API-returned ID/link within
          30 days because our upload-only permission cannot refresh it. We do
          not download or store the uploaded video back from YouTube.</LI>
        <LI><B>Payment details.</B> Payments run through Stripe. Your card
          number never touches our servers; we store only your Stripe customer
          and subscription identifiers and your plan status.</LI>
        <LI><B>Usage data.</B> Product events (sign-up, generation started or
          finished, publish, upgrade) and standard server logs, used to run
          and improve the product. We use no third-party advertising or
          cross-site trackers and show no ads.</LI>
      </UL>

      <H>Cookies, browser storage and device information</H>
      <P>
        BanterClips stores and accesses information on your browser or device
        using the strictly necessary technologies below. We do not use
        advertising cookies, cross-site tracking pixels, fingerprinting, or
        similar technology to build advertising profiles.
      </P>
      <UL>
        <LI><B>Local storage for sign-in.</B> Your browser stores a BanterClips
          session token and, when Supabase authentication is enabled, Supabase
          authentication session data needed to keep you signed in and refresh
          that session. It remains until you sign out, clear site data, or the
          session is removed or expires.</LI>
        <LI><B>Session storage for performance.</B> The trending-sports feed is
          cached in your current browser tab for up to 20 minutes so navigating
          back does not repeat the same request. The browser removes it when the
          tab session ends, and it contains no YouTube API Data.</LI>
        <LI><B>Necessary request and security data.</B> Our hosting,
          authentication and infrastructure providers (Vercel, DigitalOcean,
          Cloudflare and Supabase) receive ordinary request information such as
          IP address, browser/user-agent, timestamps and security headers when
          your device connects. Cloudflare may set a short-lived, strictly
          necessary bot-management cookie such as <code>__cf_bm</code> on our
          authentication domain. These providers process essential routing,
          security or session signals solely to deliver and protect the service.</LI>
      </UL>
      <P>
        You can remove this local information through Sign out or your browser&rsquo;s
        site-data controls. Blocking necessary browser storage may prevent sign-in.
      </P>

      <H>How we use it</H>
      <UL>
        <LI>To provide the service: generate your videos, show your library,
          publish on your explicit instruction, enforce plan limits, and bill
          your subscription.</LI>
        <LI>To generate a video, your take and creative choices are sent to
          the AI model providers listed below. They are used to produce your
          video, not to build advertising profiles.</LI>
        <LI>To send account emails (verification, password reset). No
          marketing emails without a separate opt-in.</LI>
        <LI>To keep the service safe: content checks against hate, threats and
          harassment, and abuse prevention.</LI>
      </UL>

      <H>Who processes it for us</H>
      <P>
        We share data only with the service providers that run the product,
        each bound to use it solely to provide their service to us:
      </P>
      <UL>
        <LI><B>Supabase</B> — authentication, database and video storage
          (hosted in the AWS Asia-Pacific region).</LI>
        <LI><B>Vercel</B> — web hosting. <B>DigitalOcean</B> — application
          servers. <B>Cloudflare</B> — DNS.</LI>
        <LI><B>Stripe</B> — payments and subscriptions.</LI>
        <LI><B>OpenAI</B> and <B>OpenRouter / xAI</B> — AI models that write
          the script and generate the video from your take.</LI>
        <LI><B>Meta (Instagram)</B>, <B>TikTok</B>, and <B>Google/YouTube</B> —
          receive the video and caption, title or description you selected only
          when you press Publish for that platform.</LI>
        <LI><B>Resend</B> — delivers account emails.</LI>
      </UL>
      <P>We do not sell personal data, and we do not share it with data brokers or advertisers.</P>

      <H>Google user data</H>
      <UL>
        <LI><B>Google sign-in.</B> We use your basic profile (name, email and
          picture) solely to create and authenticate your BanterClips account.</LI>
        <LI><B>YouTube publishing.</B> If you separately connect YouTube, we
          request only <code>https://www.googleapis.com/auth/youtube.upload</code>.
          Before every upload, you set and review the title, description and
          visibility (Public, Unlisted or Private). We send those exact values
          with the completed video only after you explicitly press <B>Upload to
          YouTube</B>. We do not read your existing videos, upload in the
          background, or take actions unrelated to that upload.</LI>
        <LI><B>Storage and sharing.</B> OAuth access and refresh tokens are kept
          server-side while the connection is active and are never exposed to
          the browser. The selected video and metadata are sent to Google/YouTube
          only to complete your requested upload. We retain the returned video
          ID/link for no more than 30 days as described above; we do not share
          YouTube API Data with any other third party.</LI>
        <LI><B>Limited use.</B> Google user data is never sold, used for
          advertising, or used to train AI models. Our use of information from
          Google APIs follows the <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noreferrer" style={{ color: "var(--cyan)" }}>Google API Services User Data Policy</a>,
          including its Limited Use requirements.</LI>
      </UL>

      <H>Retention and deletion</H>
      <UL>
        <LI>Your content is kept while your account is active, until you delete
          the clip or request account deletion. Deleting a clip removes its
          video files, not just the listing.</LI>
        <LI>YouTube access tokens are refreshed when they are close to expiring:
          before an upload, when connected accounts load, and by hourly
          housekeeping. This also detects grants revoked from Google settings.
          Authorization tokens are retained only while your connection is active.</LI>
        <LI>A YouTube video ID/link returned by <code>videos.insert</code> is
          deleted after no more than 30 days because we do not request the read
          permission needed to refresh it. Our own upload status, timestamp and
          the title, description and visibility you entered remain with the clip
          until you delete that clip or your account.</LI>
        <LI>Disconnecting YouTube immediately asks Google to revoke the grant
          and deletes our stored access token, refresh token, expiry, connection
          identifier and every retained YouTube video ID/link. You can also
          revoke access from
          <a href="https://security.google.com/settings/security/permissions" target="_blank" rel="noreferrer" style={{ color: "var(--cyan)" }}> Google Security settings</a>;
          our scheduled check detects that change and removes the same data.</LI>
        <LI>You can request full deletion of your account — including your
          videos, preferences, events, social connections and billing
          identifiers — by emailing <B>{CONTACT}</B>. YouTube API Data and
          authorization tokens are deleted as soon as possible and within seven
          calendar days; remaining account deletion completes within 30 days.
          Step-by-step instructions: <Link to="/data-deletion" style={{ color: "var(--cyan)" }}>Delete your data</Link>.</LI>
      </UL>

      <H>Your rights</H>
      <P>
        You can access and correct your details from your account page, and
        request a copy or deletion of your data by email. Depending on where
        you live (e.g. the EU/UK under GDPR, or India under the DPDP Act), you
        may have additional statutory rights; we honour requests from all
        users the same way.
      </P>

      <H>Security</H>
      <P>
        All traffic is encrypted in transit (TLS). Passwords are hashed, and
        social tokens are stored server-side and never exposed to the browser.
        Publishing and payment are always explicit user actions.
      </P>

      <H>Children</H>
      <P>BanterClips is not directed at children under 13, and we do not knowingly collect their data.</P>

      <H>Changes</H>
      <P>
        If this policy changes materially, we will update the date above and
        note the change in the product. Continued use after a change means
        acceptance.
      </P>
    </Layout>
  );
}

export function Terms() {
  useSeo({
    title: "Terms of Service — BanterClips",
    description:
      "The terms covering your use of BanterClips, including plan limits, acceptable use and the AI-generated parody nature of every video.",
    path: "/terms",
  });

  return (
    <Layout title="Terms of Service">
      <P>
        These terms govern your use of BanterClips. By creating an account you
        agree to them. BanterClips is currently in beta: things will change,
        and occasionally break.
      </P>

      <H>The service</H>
      <P>
        You write a sports take; we generate a short, clearly-labelled
        AI-parody video from it, which you can preview and — at your explicit
        instruction — publish to a social account you connect, or download on
        a paid plan.
      </P>

      <H>Your content</H>
      <UL>
        <LI>Your takes are yours. You grant us the licence needed to process
          them (including via the AI providers named in the Privacy Policy)
          solely to provide the service.</LI>
        <LI>You may use and publish the videos generated for you. The
          BanterClips watermark is removed only on the paid plan. Present
          generated videos as AI-generated content wherever the platform you
          publish to requires it.</LI>
        <LI>Your videos stay private to your account unless you publish them.</LI>
      </UL>

      <H>AI-generated parody</H>
      <P>
        Videos are entirely AI-generated satire and parody. They may depict
        real athletes and kits in fictional, comedic scenarios; they contain
        no real match footage or broadcast material, and they do not represent
        real events, statements, or endorsements. BanterClips is not
        affiliated with, sponsored by, or endorsed by any league, club, or
        athlete.
      </P>

      <H>Acceptable use</H>
      <UL>
        <LI>Playful rivalry is the point; hate speech, threats, harassment,
          and attacks on protected characteristics are not allowed and are
          blocked or removed.</LI>
        <LI>Do not present generated content as real news, real quotes, or
          real events, and do not use the service to defame or deceive.</LI>
        <LI>You are responsible for what you choose to publish to your own
          social accounts, and for complying with those platforms&rsquo; rules.
          Connecting a YouTube channel also means you agree to the
          <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer" style={{ color: "var(--cyan)" }}> YouTube Terms of Service</a>.</LI>
        <LI>No attempts to break, overload, or reverse-engineer the service.</LI>
      </UL>

      <H>Plans and billing</H>
      <UL>
        <LI>Free: one-time welcome credits on signup, published with a
          watermark, 720p, up to 15 seconds. Creator ($19/month): 150 credits
          monthly, 1080p available, up to 30 seconds, watermark-free downloads.
          Credit top-up packs are available to both plans and never expire.</LI>
        <LI>Credits are charged only when a video completes — failures,
          abandoned scripts and retries release the reservation in full.</LI>
        <LI>Web billing runs through Stripe; eligible iOS and Android app
          purchases run through Apple or Google. Upgrades apply after provider
          verification, and cancellation applies at the end of the paid period.
          Store subscriptions are managed in the applicable store. Your videos
          are never deleted for billing reasons.</LI>
      </UL>

      <H>Availability and liability</H>
      <P>
        The service is provided &ldquo;as is&rdquo;, without warranties, during beta. To
        the maximum extent permitted by law, our total liability for any claim
        is limited to the amount you paid us in the three months before the
        claim. Nothing in these terms limits liability that cannot lawfully be
        limited.
      </P>

      <H>Termination</H>
      <P>
        You can delete your account at any time (see the Privacy Policy). We
        may suspend accounts that violate these terms, with notice where
        practical.
      </P>

      <H>Changes</H>
      <P>
        We may update these terms as the product evolves; material changes
        will be noted in the product. Continued use after a change means
        acceptance.
      </P>
    </Layout>
  );
}


/**
 * Data deletion instructions — the public URL Meta (Instagram/Facebook)
 * App Review requires under "User data deletion", and the same page linked
 * from the privacy policy. Every step here must stay true of the product:
 * Disconnect really does purge the tokens (routers/socials.py), and account
 * deletion is handled by support within 30 days.
 */
export function DataDeletion() {
  useSeo({
    title: "Delete your data — BanterClips",
    description:
      "How to delete the data BanterClips holds about you: disconnect Instagram, TikTok or YouTube instantly, or delete your whole account.",
    path: "/data-deletion",
  });
  return (
    <Layout title="Delete your data">
      <P>
        You can remove what BanterClips holds about you at any time — either the
        connection to one social account, or your entire BanterClips account and
        everything in it. This page is also the data-deletion instructions we
        provide to Meta (Instagram and Facebook), TikTok and Google.
      </P>

      <H>What we store when you connect Instagram or Facebook</H>
      <P>
        Only what publishing needs: your Instagram account ID and username, and the
        access token Meta issues to BanterClips. We use it for one thing — posting
        a clip to your account when you explicitly press Publish. We never read your
        messages, followers or feed, and we never post without that press.
      </P>

      <span id="request-copy" />
      <H>Request a copy of your data</H>
      <P>
        Email <a href={`mailto:${CONTACT}?subject=Data%20export%20request`} style={{ color: "var(--cyan)" }}>{CONTACT}</a> from
        the address on your account with the subject <B>“Data export request”</B>.
        After verifying the request, we provide a copy of the account and
        content information BanterClips holds about you.
      </P>

      <span id="disconnect" />
      <H>Option 1 — Disconnect one platform (immediate)</H>
      <UL>
        <LI>Sign in to BanterClips and open <B>Account → Connected accounts</B>.</LI>
        <LI>Press <B>Disconnect</B> next to Instagram, TikTok or YouTube.</LI>
        <LI>The stored access token, refresh token, expiry and platform account ID
          are deleted <B>immediately</B>, and the platform is told to revoke the
          grant. Your BanterClips account and videos stay.</LI>
        <LI>You can also remove BanterClips from the platform's side: Instagram
          <B> Settings → Apps and websites</B>, Facebook <B>Settings → Business
          integrations</B>, TikTok <B>Settings → Security → Manage app
          permissions</B>, or your
          <a href="https://security.google.com/settings/security/permissions" target="_blank" rel="noreferrer" style={{ color: "var(--cyan)" }}> Google Security settings</a>.
          Doing that invalidates the token on their end; press Disconnect in
          BanterClips too so the record is removed here as well.</LI>
      </UL>

      <H>Option 2 — Delete your whole BanterClips account</H>
      <UL>
        <LI>Email <B>{CONTACT}</B> from the address you signed up with, with the
          subject <B>“Delete my account”</B>.</LI>
        <LI>We delete your videos and their files, scripts, preferences, connected
          social accounts and their tokens, usage events, feedback, and your
          billing identifiers at Stripe, Apple, or Google. YouTube API Data and
          authorization tokens are removed as soon as possible and within
          <B> seven calendar days</B>; the rest of the deletion completes within
          <B> 30 days</B>. We confirm by email when it is done.</LI>
        <LI>Anything you already published to Instagram, TikTok or YouTube lives on
          those platforms under your account and is not affected — delete it there
          if you want it gone.</LI>
      </UL>

      <H>Removed BanterClips from Facebook or Instagram already?</H>
      <P>
        Meta invalidates the token the moment you remove the app there, so
        BanterClips can no longer act on your account. To have the remaining
        record (account ID and username) purged as well, use Option 1 or email
        us under Option 2 — we will confirm once it is gone.
      </P>

      <H>What we keep after deletion</H>
      <P>
        Nothing that identifies you. The only records that survive are the ones
        the law requires — Stripe's payment records for invoices already issued,
        kept by Stripe under its own retention policy.
      </P>
    </Layout>
  );
}
