import Link from "next/link";
import { PageHeader } from "@/components/page-header";
export default function NotFound(){return <div className="empty-state"><div><PageHeader eyebrow="404 · PAGE NOT FOUND" title="This page isn’t here" description="The link may have changed. Return home or explore the public education pages."/><Link className="btn" href="/">Go to home</Link></div></div>;}
