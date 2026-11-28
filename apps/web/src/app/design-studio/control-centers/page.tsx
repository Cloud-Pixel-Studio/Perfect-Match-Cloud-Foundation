import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ControlCenterPreview } from "../../../components/control-center-preview";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Control center preview",
  robots: { index: false, follow: false },
};

export default function ControlCenterDesignPage() {
  if (process.env.PMQMS_CONTROL_PREVIEW !== "1") notFound();
  return <ControlCenterPreview />;
}
