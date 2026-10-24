import { BeadRow } from "./beads";

/** Page title, an optional line under it, the bead row, and room for an action. */
export function PageHeader({ title, sub, action, crumbs }: {
  title: React.ReactNode;
  sub?: React.ReactNode;
  action?: React.ReactNode;
  crumbs?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4">
      {crumbs && <nav aria-label="Breadcrumb" className="text-[15px] text-muted">{crumbs}</nav>}
      <header className="flex flex-wrap items-end justify-between gap-5">
        <div className="flex flex-col gap-2">
          <h1 className="text-[40px] sm:text-[52px]">{title}</h1>
          {sub && <p className="text-[17px] text-muted">{sub}</p>}
        </div>
        {action}
      </header>
      <BeadRow />
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
