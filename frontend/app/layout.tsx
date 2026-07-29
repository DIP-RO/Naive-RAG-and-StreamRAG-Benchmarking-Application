import './globals.css';

export const metadata = {
  title: 'StreamRAG vs Naive RAG',
  description: 'Production take-home assessment demonstrating benchmarkable RAG patterns.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
