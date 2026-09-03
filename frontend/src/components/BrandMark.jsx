export default function BrandMark({ size = 28, style }) {
  return (
    <img
      src="/icon-192.png?v=2"
      alt=""
      width={size}
      height={size}
      style={{ display: "block", flexShrink: 0, ...style }}
    />
  );
}
