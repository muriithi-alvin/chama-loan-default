import { BeadArc } from "./beads";

const HEADER_TONES = { cream: "bg-cream", ice: "bg-ice" } as const;

/** Page title in a colour block with a bead-collar corner and a beaded edge,
 * an optional line under it, room for an action and an optional figurine. */
export function PageHeader({ title, sub, action, crumbs, tone = "cream", art }: {
  title: React.ReactNode;
  sub?: React.ReactNode;
  action?: React.ReactNode;
  crumbs?: React.ReactNode;
  tone?: keyof typeof HEADER_TONES;
  art?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3">
      {crumbs && <nav aria-label="Breadcrumb" className="text-[15px] text-muted">{crumbs}</nav>}
      <header className={`relative overflow-hidden rounded-card px-6 pb-9 pt-7 sm:px-8 ${HEADER_TONES[tone]}`}>
        <BeadArc className="pointer-events-none absolute -right-16 -top-20 h-[230px] w-[230px] sm:-right-10" />
        {art && <div aria-hidden="true" className="pointer-events-none absolute bottom-4 right-[230px] hidden opacity-70 xl:block">{art}</div>}
        <div className="relative flex flex-wrap items-end justify-between gap-5 pr-24 sm:pr-36">
          <div className="flex max-w-[44em] flex-col gap-2">
            <h1 className="text-[38px] sm:text-[50px]">{title}</h1>
            {sub && <p className="text-[17px] text-subtle">{sub}</p>}
          </div>
          {action}
        </div>
        <div aria-hidden="true" className="bead-edge absolute inset-x-0 bottom-0" />
      </header>
    </div>
  );
}

/** The content column of every page: up to 1,200 px wide (section 7). */
export function PageBody({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <main id="main" tabIndex={-1} className={`relative mx-auto flex w-full max-w-[1200px] flex-col gap-7 px-4 py-7 sm:px-8 lg:px-11 lg:py-9 focus:outline-none ${className}`}>
      {children}
    </main>
  );
}

export function Card({ children, className = "", tone = "paper", ...rest }: {
  children: React.ReactNode;
  className?: string;
  tone?: "paper" | "ice" | "cream";
} & React.HTMLAttributes<HTMLElement>) {
  const tones = { paper: "border border-line bg-white", ice: "bg-ice", cream: "bg-cream" };
  return (
    <section className={`rounded-card p-6 sm:p-7 ${tones[tone]} ${className}`} {...rest}>
      {children}
    </section>
  );
}
