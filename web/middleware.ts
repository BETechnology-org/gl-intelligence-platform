import { NextResponse, type NextRequest } from "next/server";
import { updateSession } from "./utils/supabase/middleware";

export async function middleware(request: NextRequest) {
  // Supabase magic-link callbacks: if the OAuth `code` lands on any path
  // other than /auth/callback (because the redirect URL isn't in the
  // project's allowlist), forward it to /auth/callback preserving the
  // code + a sensible post-auth redirect target.
  const code = request.nextUrl.searchParams.get("code");
  const path = request.nextUrl.pathname;
  if (code && path !== "/auth/callback") {
    const url = request.nextUrl.clone();
    url.pathname = "/auth/callback";
    // Carry through any explicit redirect param; default to /dashboard.
    if (!url.searchParams.has("redirect")) {
      url.searchParams.set("redirect", "/dashboard");
    }
    return NextResponse.redirect(url);
  }

  return await updateSession(request);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|icon.svg|manifest.webmanifest|.*\\.(?:svg|png|jpg|jpeg|gif|webp|gltf|glb|woff2?|ttf|otf)$).*)",
  ],
};
