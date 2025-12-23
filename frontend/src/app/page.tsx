import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { BookOpen, Mic, Users, Sparkles } from 'lucide-react';

export default function LandingPage() {
  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-primary" />
            <span className="font-serif text-xl font-semibold">Memoir</span>
          </Link>
          <nav className="flex items-center gap-4">
            <Link href="/auth/login">
              <Button variant="ghost">Sign In</Button>
            </Link>
            <Link href="/auth/register">
              <Button>Get Started</Button>
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="container mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
          Your Story Deserves
          <br />
          <span className="text-primary">To Be Told</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
          Capture your life's journey through simple voice recordings. 
          Our AI weaves your memories into a beautiful, printed book 
          that your family will treasure forever.
        </p>
        <div className="mt-10 flex justify-center gap-4">
          <Link href="/auth/register">
            <Button size="lg" className="gap-2">
              <Sparkles className="h-4 w-4" />
              Start Your Story
            </Button>
          </Link>
          <Link href="#how-it-works">
            <Button size="lg" variant="outline">
              See How It Works
            </Button>
          </Link>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="border-t bg-muted/50 py-20">
        <div className="container mx-auto px-4">
          <h2 className="text-center font-serif text-3xl font-bold">
            Three Simple Steps
          </h2>
          <div className="mt-12 grid gap-8 md:grid-cols-3">
            <div className="rounded-lg bg-card p-6 text-center shadow-sm">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <Mic className="h-6 w-6 text-primary" />
              </div>
              <h3 className="font-semibold">1. Record Your Memories</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Answer questions about your life through simple voice recordings. 
                Just talk naturally — we'll handle the rest.
              </p>
            </div>
            <div className="rounded-lg bg-card p-6 text-center shadow-sm">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <Sparkles className="h-6 w-6 text-primary" />
              </div>
              <h3 className="font-semibold">2. AI Creates Your Story</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Our AI transforms your recordings into beautifully written 
                chapters, preserving your voice and personality.
              </p>
            </div>
            <div className="rounded-lg bg-card p-6 text-center shadow-sm">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <BookOpen className="h-6 w-6 text-primary" />
              </div>
              <h3 className="font-semibold">3. Share Your Legacy</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Review, edit, and publish your memoir. Print beautiful 
                hardcover books for your family.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Family */}
      <section className="py-20">
        <div className="container mx-auto px-4">
          <div className="mx-auto max-w-3xl text-center">
            <Users className="mx-auto h-12 w-12 text-primary" />
            <h2 className="mt-4 font-serif text-3xl font-bold">
              Include Family & Friends
            </h2>
            <p className="mt-4 text-muted-foreground">
              Invite loved ones to contribute their own memories and perspectives. 
              Create a richer story by weaving together multiple voices.
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t bg-primary py-16 text-primary-foreground">
        <div className="container mx-auto px-4 text-center">
          <h2 className="font-serif text-3xl font-bold">
            Ready to Start Your Story?
          </h2>
          <p className="mx-auto mt-4 max-w-xl opacity-90">
            Join thousands of families preserving their legacies. 
            Your first chapter is free.
          </p>
          <Link href="/auth/register">
            <Button size="lg" variant="secondary" className="mt-8">
              Begin Your Memoir
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="container mx-auto flex flex-col items-center justify-between gap-4 px-4 text-sm text-muted-foreground md:flex-row">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4" />
            <span>Memoir</span>
          </div>
          <div className="flex gap-6">
            <Link href="/privacy" className="hover:text-foreground">Privacy</Link>
            <Link href="/terms" className="hover:text-foreground">Terms</Link>
            <Link href="/contact" className="hover:text-foreground">Contact</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

