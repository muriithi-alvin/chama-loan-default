import { NextResponse, type NextRequest } from "next/server";

// A quick first check only: with no session cookie at all, go straight to
// sign-in. The Python API checks the session and role on every request (R4).
export function proxy(request: NextRequest) {
  if (!request.cookies.has("chama_session")) {
    const url = request.nextUrl.clone();
    url.pathname = "/signin";
    url.search = `?next=${encodeURIComponent(request.nextUrl.pathname + request.nextUrl.search)}`;
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/o/:path*", "/m/:path*", "/o", "/m"] };
