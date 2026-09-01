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

const EFFECTIVE = "September 1, 2026";
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
          needed to publish. For YouTube this includes an access token, refresh
          token and expiry for the <code>youtube.upload</code> permission. We do
          not read your existing YouTube videos or channel content, and nothing
          is ever posted automatically.</LI>
        <LI><B>Payment details.</B> Payments run through Stripe. Your card
          number never touches our servers; we store only your Stripe customer
          and subscription identifiers and your plan status.</LI>
        <LI><B>Usage data.</B> Product events (sign-up, generation started or
          finished, publish, upgrade) and standard server logs, used to run
          and improve the product. We use no third-party advertising or
          cross-site trackers and show no ads.</LI>
      </UL>

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
          We use it solely to upload the completed video, title and description
          you selected after you explicitly press Publish. We do not read your
          existing videos, publish in the background, or take actions unrelated
          to that upload.</LI>
        <LI><B>Storage and sharing.</B> OAuth access and refresh tokens are kept
          server-side while the connection is active and are never exposed to
          the browser. The selected video and metadata are sent to Google/YouTube
          only to complete your requested upload.</LI>
        <LI><B>Limited use.</B> Google user data is never sold, used for
          advertising, or used to train AI models. Our use of information from
          Google APIs follows the <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noreferrer" style={{ color: "var(--cyan)" }}>Google API Services User Data Policy</a>,
          including its Limited Use requirements.</LI>
      </UL>

      <H>Retention and deletion</H>
      <UL>
        <LI>Your content is kept while your account is active. Deleting a clip
          removes its video files, not just the listing.</LI>
        <LI>Disconnecting a social account immediately deletes its stored access
          token, refresh token, expiry and platform identifier. Publish history
          remains with the clip until you delete that clip or your account.</LI>
        <LI>You can also revoke Google access at any time from your
          <a href="https://myaccount.google.com/connections" target="_blank" rel="noreferrer" style={{ color: "var(--cyan)" }}> Google Account connections</a>.</LI>
        <LI>You can request full deletion of your account — including your
          videos, preferences, events, and billing identity at Stripe — by
          emailing <B>{CONTACT}</B>. We complete deletion within 30 days.</LI>
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
          social accounts, and for complying with those platforms&rsquo; rules.</LI>
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
        <LI>Billing runs through Stripe. Upgrades apply immediately;
          cancellation applies at the end of the paid period. Your videos are
          never deleted for billing reasons.</LI>
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
