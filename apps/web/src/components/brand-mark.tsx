import Image from "next/image";

type BrandMarkProps = {
  className?: string;
  priority?: boolean;
  size?: number;
};

export function BrandMark({ className = "", priority = false, size = 40 }: BrandMarkProps) {
  return (
    <span
      aria-hidden="true"
      className={`brand-mark ${className}`.trim()}
      style={{ blockSize: size, inlineSize: size }}
    >
      <Image
        alt=""
        className="brand-mark-light"
        height={size}
        priority={priority}
        src="/brand/selected/pmqms-mark.svg"
        unoptimized
        width={size}
      />
      <Image
        alt=""
        className="brand-mark-dark"
        height={size}
        priority={priority}
        src="/brand/selected/pmqms-mark-dark.svg"
        unoptimized
        width={size}
      />
    </span>
  );
}
