import type { APIRoute } from "astro";
import { entries } from "../lib/data";

export const GET: APIRoute = () => new Response(JSON.stringify(entries), { headers: { "Content-Type": "application/json" } });
