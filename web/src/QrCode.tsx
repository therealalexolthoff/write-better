// A QR code drawn as an SVG, for scanning with an authenticator app.
// qrcode-generator only works out which squares are dark; React draws them,
// so no generated HTML is ever injected into the page.
import qrcode from "qrcode-generator";

export default function QrCode({ text, label, size = 200 }: { text: string; label: string; size?: number }) {
  const qr = qrcode(0, "M"); // 0: the smallest version that fits the text
  qr.addData(text);
  qr.make();
  const count = qr.getModuleCount();
  const quiet = 2; // the blank border scanners need
  let path = "";
  for (let row = 0; row < count; row++) {
    for (let col = 0; col < count; col++) {
      if (qr.isDark(row, col)) path += `M${col + quiet} ${row + quiet}h1v1h-1z`;
    }
  }
  const side = count + quiet * 2;
  return (
    <svg
      className="qr-code"
      role="img"
      aria-label={label}
      width={size}
      height={size}
      viewBox={`0 0 ${side} ${side}`}
      shapeRendering="crispEdges"
    >
      <rect width={side} height={side} fill="#fff" />
      <path d={path} fill="#1f2426" />
    </svg>
  );
}
