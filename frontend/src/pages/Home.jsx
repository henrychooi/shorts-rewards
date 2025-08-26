import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "../components/ui/avatar";
import { Input } from "../components/ui/input";
import { Play, Users, Heart, Search, Video } from "lucide-react";

function App() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-2xl font-bold text-foreground">StreamHub</h1>
            <nav className="hidden md:flex items-center gap-6">
              <a
                href="#"
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                Browse
              </a>
              <a
                href="#"
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                Following
              </a>
              <a
                href="#"
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                Categories
              </a>
            </nav>
          </div>

          <div className="flex items-center gap-4">
            <div className="relative hidden sm:block">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
              <Input placeholder="Search streams..." className="pl-10 w-64" />
            </div>
            <Button variant="outline" size="sm">
              <Video className="w-4 h-4 mr-2" />
              Go Live
            </Button>
            <Avatar>
              <AvatarImage src="/diverse-user-avatars.png" />
              <AvatarFallback>U</AvatarFallback>
            </Avatar>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="bg-gradient-to-r from-primary/10 to-accent/10 py-16">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-4xl md:text-6xl font-bold text-foreground mb-6">
            Stream Your Passion
          </h2>
          <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
            Connect with your audience in real-time. Share your creativity,
            build your community, and grow your brand.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="bg-accent hover:bg-accent/90">
              <Play className="w-5 h-5 mr-2" />
              Start Streaming
            </Button>
            <Button variant="outline" size="lg">
              Watch Live Streams
            </Button>
          </div>
        </div>
      </section>

      {/* Featured Streams */}
      <section className="py-12">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between mb-8">
            <h3 className="text-2xl font-bold text-foreground">
              Featured Streams
            </h3>
            <Button variant="ghost">View All</Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Card
                key={i}
                className="group cursor-pointer hover:shadow-lg transition-all duration-300"
              >
                <div className="relative">
                  <img
                    src={`/gaming-stream-.png?height=200&width=400&query=gaming stream ${i}`}
                    alt={`Stream ${i}`}
                    className="w-full h-48 object-cover rounded-t-lg"
                  />
                  <Badge className="absolute top-2 left-2 bg-red-500 hover:bg-red-500">
                    <div className="w-2 h-2 bg-white rounded-full mr-1 animate-pulse"></div>
                    LIVE
                  </Badge>
                  <div className="absolute top-2 right-2 bg-black/70 text-white px-2 py-1 rounded text-sm">
                    <Users className="w-3 h-3 inline mr-1" />
                    {Math.floor(Math.random() * 5000) + 100}
                  </div>
                </div>
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <Avatar className="w-10 h-10">
                      <AvatarImage
                        src={`/streamer-.png?height=40&width=40&query=streamer ${i}`}
                      />
                      <AvatarFallback>S{i}</AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                      <h4 className="font-semibold text-foreground group-hover:text-accent transition-colors">
                        Epic Gaming Session #{i}
                      </h4>
                      <p className="text-sm text-muted-foreground">
                        StreamerName{i}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Gaming • English
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Categories */}
      <section className="py-12 bg-muted/30">
        <div className="container mx-auto px-4">
          <h3 className="text-2xl font-bold text-foreground mb-8">
            Browse Categories
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {[
              { name: "Gaming", viewers: "1.2M", image: "gaming category" },
              { name: "Music", viewers: "450K", image: "music category" },
              { name: "Art", viewers: "230K", image: "art category" },
              { name: "Cooking", viewers: "180K", image: "cooking category" },
              { name: "Tech", viewers: "320K", image: "tech category" },
              { name: "Fitness", viewers: "150K", image: "fitness category" },
            ].map((category) => (
              <Card
                key={category.name}
                className="group cursor-pointer hover:shadow-md transition-all"
              >
                <div className="relative">
                  <img
                    src={`/abstract-geometric-shapes.png?height=120&width=200&query=${category.image}`}
                    alt={category.name}
                    className="w-full h-24 object-cover rounded-t-lg"
                  />
                  <div className="absolute inset-0 bg-black/40 rounded-t-lg flex items-center justify-center">
                    <div className="text-center text-white">
                      <h4 className="font-semibold">{category.name}</h4>
                      <p className="text-xs opacity-90">
                        {category.viewers} viewers
                      </p>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Creator Spotlight */}
      <section className="py-12">
        <div className="container mx-auto px-4">
          <h3 className="text-2xl font-bold text-foreground mb-8">
            Top Creators
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[1, 2, 3, 4].map((i) => (
              <Card
                key={i}
                className="text-center p-6 hover:shadow-lg transition-all"
              >
                <Avatar className="w-20 h-20 mx-auto mb-4">
                  <AvatarImage
                    src={`/top-creator-.png?height=80&width=80&query=top creator ${i}`}
                  />
                  <AvatarFallback>TC{i}</AvatarFallback>
                </Avatar>
                <h4 className="font-semibold text-foreground mb-2">
                  TopCreator{i}
                </h4>
                <p className="text-sm text-muted-foreground mb-3">
                  Gaming • Entertainment
                </p>
                <div className="flex items-center justify-center gap-4 text-sm text-muted-foreground mb-4">
                  <span className="flex items-center gap-1">
                    <Users className="w-4 h-4" />
                    {Math.floor(Math.random() * 100)}K
                  </span>
                  <span className="flex items-center gap-1">
                    <Heart className="w-4 h-4" />
                    {Math.floor(Math.random() * 50)}K
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full bg-transparent"
                >
                  Follow
                </Button>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-12 bg-primary text-primary-foreground">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 text-center">
            <div>
              <div className="text-3xl font-bold mb-2">2.5M+</div>
              <div className="text-primary-foreground/80">Active Streamers</div>
            </div>
            <div>
              <div className="text-3xl font-bold mb-2">15M+</div>
              <div className="text-primary-foreground/80">Monthly Viewers</div>
            </div>
            <div>
              <div className="text-3xl font-bold mb-2">500K+</div>
              <div className="text-primary-foreground/80">
                Hours Streamed Daily
              </div>
            </div>
            <div>
              <div className="text-3xl font-bold mb-2">50+</div>
              <div className="text-primary-foreground/80">Categories</div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-card border-t border-border py-12">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div>
              <h4 className="font-bold text-foreground mb-4">StreamHub</h4>
              <p className="text-muted-foreground text-sm">
                The ultimate platform for content creators and viewers to
                connect and share amazing experiences.
              </p>
            </div>
            <div>
              <h5 className="font-semibold text-foreground mb-4">Platform</h5>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <a
                    href="#"
                    className="hover:text-foreground transition-colors"
                  >
                    Browse Streams
                  </a>
                </li>
                <li>
                  <a
                    href="#"
                    className="hover:text-foreground transition-colors"
                  >
                    Categories
                  </a>
                </li>
                <li>
                  <a
                    href="#"
                    className="hover:text-foreground transition-colors"
                  >
                    Mobile App
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <h5 className="font-semibold text-foreground mb-4">Creators</h5>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <a
                    href="#"
                    className="hover:text-foreground transition-colors"
                  >
                    Creator Dashboard
                  </a>
                </li>
                <li>
                  <a
                    href="#"
                    className="hover:text-foreground transition-colors"
                  >
                    Monetization
                  </a>
                </li>
                <li>
                  <a
                    href="#"
                    className="hover:text-foreground transition-colors"
                  >
                    Analytics
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <h5 className="font-semibold text-foreground mb-4">Support</h5>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <a
                    href="#"
                    className="hover:text-foreground transition-colors"
                  >
                    Help Center
                  </a>
                </li>
                <li>
                  <a
                    href="#"
                    className="hover:text-foreground transition-colors"
                  >
                    Community
                  </a>
                </li>
                <li>
                  <a
                    href="#"
                    className="hover:text-foreground transition-colors"
                  >
                    Contact Us
                  </a>
                </li>
              </ul>
            </div>
          </div>
          <div className="border-t border-border mt-8 pt-8 text-center text-sm text-muted-foreground">
            <p>&copy; 2024 StreamHub. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
