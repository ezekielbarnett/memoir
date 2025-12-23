'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { auth, projects, isAuthenticated, type User, type Project } from '@/lib/api';
import { BookOpen, Plus, Mic, FileText, LogOut, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [projectList, setProjectList] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push('/auth/login');
      return;
    }
    
    loadData();
  }, [router]);

  async function loadData() {
    try {
      const [userData, projectsData] = await Promise.all([
        auth.me(),
        projects.list(),
      ]);
      setUser(userData);
      setProjectList(projectsData);
    } catch (error) {
      toast.error('Failed to load data');
      router.push('/auth/login');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateProject() {
    setCreating(true);
    try {
      const project = await projects.create('My Life Story');
      toast.success('Project created!');
      setProjectList([project, ...projectList]);
    } catch (error) {
      toast.error('Failed to create project');
    } finally {
      setCreating(false);
    }
  }

  async function handleLogout() {
    await auth.logout();
    router.push('/');
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted/30">
      {/* Header */}
      <header className="border-b bg-background">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Link href="/dashboard" className="flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-primary" />
            <span className="font-serif text-xl font-semibold">Memoir</span>
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">
              {user?.name}
            </span>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="container mx-auto px-4 py-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="font-serif text-3xl font-bold">Your Stories</h1>
            <p className="mt-1 text-muted-foreground">
              Create and manage your life story projects
            </p>
          </div>
          <Button onClick={handleCreateProject} disabled={creating}>
            {creating ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Plus className="mr-2 h-4 w-4" />
            )}
            New Story
          </Button>
        </div>

        {projectList.length === 0 ? (
          <Card className="text-center">
            <CardHeader>
              <CardTitle>Start Your First Story</CardTitle>
              <CardDescription>
                Create a project to begin capturing your memories
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={handleCreateProject} disabled={creating}>
                {creating ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="mr-2 h-4 w-4" />
                )}
                Create My Life Story
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {projectList.map((project) => (
              <Link key={project.id} href={`/project/${project.id}`}>
                <Card className="cursor-pointer transition-shadow hover:shadow-md">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <FileText className="h-5 w-5 text-primary" />
                      {project.name}
                    </CardTitle>
                    <CardDescription>
                      Created {new Date(project.created_at).toLocaleDateString()}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" className="gap-1">
                        <Mic className="h-3 w-3" />
                        Record
                      </Button>
                      <Button size="sm" variant="outline" className="gap-1">
                        <FileText className="h-3 w-3" />
                        View
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

