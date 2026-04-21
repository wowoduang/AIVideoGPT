import { cn } from '@/lib/utils';

type Props = {
  size?: number;
  className?: string;
  showText?: boolean;
};

export function BrandLogo({ size = 28, className, showText = true }: Props) {
  return (
    <div className={cn('flex items-center gap-2 select-none', className)}>
      <div
        className="relative flex items-center justify-center rounded-full"
        style={{
          width: size,
          height: size,
          background: 'radial-gradient(circle at 30% 30%, #7dff4d, #2cb90a 70%)',
          boxShadow: '0 0 16px rgba(70, 236, 19, 0.45)',
        }}
      >
        <svg
          width={size * 0.55}
          height={size * 0.55}
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M8 5l10 7-10 7V5z"
            fill="#060a07"
          />
        </svg>
      </div>
      {showText ? (
        <span className="text-base font-bold tracking-tight text-white">
          AIVideoGPT
        </span>
      ) : null}
    </div>
  );
}

export default BrandLogo;
