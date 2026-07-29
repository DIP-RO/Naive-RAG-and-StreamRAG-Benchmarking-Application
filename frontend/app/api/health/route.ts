export async function GET() {
  const backend = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api';
  return Response.json({ status: 'ok', backend });
}
