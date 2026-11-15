import type { Metadata } from "next";
import { ReliabilityDashboard } from "@/components/reliability-dashboard";
export const metadata: Metadata = { title: "Model reliability & sensitivity" };
export default function Page() { return <ReliabilityDashboard/>; }
