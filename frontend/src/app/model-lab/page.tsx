import type { Metadata } from "next";
import { ModelLab } from "@/components/model-lab";
export const metadata: Metadata = { title: "Model lab" };
export default function Page() { return <ModelLab/>; }
