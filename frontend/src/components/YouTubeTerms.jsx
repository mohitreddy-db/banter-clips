/**
 * The disclosure YouTube's API Services Developer Policies require wherever a
 * channel can be connected: a statement that the feature uses YouTube API
 * Services, plus links to the YouTube Terms of Service and the Google Privacy
 * Policy. It sits beside the connect control on the Account page and in the
 * publish dialog, and is repeated in our own privacy policy.
 */
export function YouTubeTerms({ style }) {
  const link = { color: "var(--app-cyan)", textDecoration: "none" };
  return (
    <div style={{ fontSize: 11.5, color: "var(--app-muted2)", lineHeight: 1.5, ...style }}>
      Uses YouTube API Services ·{" "}
      <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer" style={link}>YouTube Terms of Service</a>
      {" · "}
      <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer" style={link}>Google Privacy Policy</a>
    </div>
  );
}
