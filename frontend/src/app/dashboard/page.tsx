import type { Metadata } from "next";
import { AccountDashboard } from "@/components/account-dashboard";
import { requireUser } from "@/lib/require-user";
export const metadata: Metadata = { title: "My dashboard" };
export const dynamic = "force-dynamic";
export default async function Page(){const user=await requireUser("/dashboard");return <AccountDashboard email={user.email}/>;}
