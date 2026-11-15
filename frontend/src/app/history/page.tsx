import type { Metadata } from "next";
import { HistoryManager } from "@/components/history-manager";
import { requireUser } from "@/lib/require-user";
export const metadata: Metadata = { title: "My history" };
export const dynamic = "force-dynamic";
export default async function Page(){await requireUser("/history");return <HistoryManager/>;}
