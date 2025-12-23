import type { Metadata } from 'next';
import { Crimson_Pro, Source_Sans_3 } from 'next/font/google';
import { ThemeProvider } from '@/components/theme-provider';
import { Toaster } from '@/components/ui/sonner';
import './globals.css';

const fontSerif = Crimson_Pro({
  subsets: ['latin'],
  variable: '--font-serif',
  display: 'swap',
});

const fontSans = Source_Sans_3({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Memoir - Capture Your Life Story',
  description: 'Create beautiful, personalized life stories with the help of AI.',
  keywords: ['memoir', 'life story', 'biography', 'autobiography', 'family history'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${fontSans.variable} ${fontSerif.variable} font-sans antialiased`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          disableTransitionOnChange
        >
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}

