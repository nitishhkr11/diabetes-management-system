"use client";
import Link from "next/link";
export default function ErrorPage({reset}:{error:Error&{digest?:string};reset:()=>void}){return <div className="empty-state"><div><div className="eyebrow">TEMPORARY ISSUE</div><h1>We couldn’t load this page</h1><p>Try again. If the problem continues, check whether the research API is available.</p><button className="btn" onClick={reset}>Try again</button> <Link className="btn btn-secondary" href="/">Return home</Link></div></div>;}
