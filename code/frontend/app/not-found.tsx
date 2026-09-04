import Link from "next/link";

export default function NotFound() {
  return <div className="state-box"><div><h2>Page not found</h2>
    <p>The requested application route does not exist.</p>
    <Link className="button" href="/">Return to overview</Link></div></div>;
}
