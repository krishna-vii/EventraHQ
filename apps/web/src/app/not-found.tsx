import Link from "next/link";
import { Shell } from "../components/marketplace";
export default function NotFound() { return <Shell><div className="container empty-state"><h1>This page missed its cue.</h1><p>Let’s find you a better stage.</p><Link href="/artists" className="button">Explore artists</Link></div></Shell>; }
