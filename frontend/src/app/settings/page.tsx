import type { Metadata } from "next";
import { createClient } from "@/lib/supabase/server";
import { requireUser } from "@/lib/require-user";
import { AccountSettings } from "@/components/account-settings";
export const metadata: Metadata = { title: "Account & privacy settings" };
export const dynamic = "force-dynamic";
export default async function Page(){await requireUser("/settings");const supabase=await createClient();const {data}=supabase?await supabase.auth.getUser():{data:null};return <AccountSettings email={data?.user?.email||"Account"}/>;}
