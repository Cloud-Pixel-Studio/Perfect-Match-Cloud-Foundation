import Image from "next/image";

type BrandMarkProps = {
  className?: string;
  priority?: boolean;
  size?: 26 | 40;
  variant?: "perfect-match" | "bems-quality";
};

export function BrandMark({ className = "", priority = false, size = 40, variant = "perfect-match" }: BrandMarkProps) {
  return (
    <span
      aria-hidden="true"
      className={`brand-mark brand-mark-${size} ${className}`.trim()}
    >
      <Image
        alt=""
        className="brand-mark-light"
        height={size}
        priority={priority}
        src={variant === "bems-quality" ? "/brand/selected/bems-quality-mark.svg" : "/brand/selected/pmqms-mark.svg"}
        unoptimized
        width={size}
      />
      <Image
        alt=""
        className="brand-mark-dark"
        height={size}
        priority={priority}
        src={variant === "bems-quality" ? "/brand/selected/bems-quality-mark-dark.svg" : "/brand/selected/pmqms-mark-dark.svg"}
        unoptimized
        width={size}
      />
    </span>
  );
}
