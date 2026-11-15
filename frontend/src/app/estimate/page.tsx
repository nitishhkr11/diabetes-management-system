import type { Metadata } from "next";
import { Estimator } from "@/components/estimator";
import { createClient } from "@/lib/supabase/server";
export const metadata: Metadata = { title: "Educational estimator" };
export const dynamic = "force-dynamic";
export default async function Page() {
  const supabase=await createClient(); const {data}=supabase?await supabase.auth.getClaims():{data:null};
  return <Estimator authenticated={Boolean(data?.claims?.sub)}/>;
}
