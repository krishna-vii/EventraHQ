"use client";

import { useEffect, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {
  ArrowDown, ArrowRight, AudioLines, Check, ChevronDown, Command, Compass,
  Heart, MapPin, Menu, Mic2, Music2, Plus, Radio, Search, SlidersHorizontal,
  Sparkles, Square, Star, Terminal, WandSparkles, X,
} from "lucide-react";

type Artist = {
  id: string; slug: string; name: string; category: string; city: string;
  price_paise: number; rating: number; review_count: number; tagline: string;
  description: string; tags: string[]; accent: string; available: boolean;
};
type Health = { data_mode?: string; services?: Record<string, { status: string; message?: string }> };
type Brief = { name: string; city: string; date: string; budget: string; notes: string };
type Answer = { message: string; artist_ids: string[] };
const EMPTY_BRIEF: Brief = { name: "", city: "Bengaluru", date: "", budget: "", notes: "" };
const CATEGORIES = ["All artists", "Live band", "DJ", "Vocalist", "Instrumental"];
const CITIES = ["All cities", "Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Pune", "Chennai"];
const money = (paise: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);

function ArtistArtwork({ artist, large = false }: { artist: Artist; large?: boolean }) {
  const variant = artist.category === "DJ" ? "vinyl" : artist.category === "Vocalist" ? "voice" : artist.category === "Instrumental" ? "keys" : "stage";
  return <div className={`artist-art ${artist.accent || "teal"} art-${variant} ${large ? "art-large" : ""}`} aria-hidden="true">
    <div className="art-grid" /><div className="art-orb orb-one" /><div className="art-orb orb-two" />
    {variant === "vinyl" ? <div className="vinyl-disc"><div className="vinyl-label"><AudioLines size={28} strokeWidth={1.5} /></div></div>
      : variant === "voice" ? <div className="voice-scene"><div className="voice-ring" /><Mic2 size={92} strokeWidth={1} /><div className="voice-line" /></div>
      : variant === "keys" ? <div className="piano-scene">{Array.from({ length: 11 }, (_, i) => <span key={i} className={i % 3 !== 0 ? "has-black" : ""} />)}</div>
      : <div className="stage-scene"><div className="stage-beam beam-one" /><div className="stage-beam beam-two" /><div className="stage-beam beam-three" /><div className="wave-bars">{Array.from({ length: 19 }, (_, i) => <i key={i} style={{ height: `${18 + ((i * 37 + 17) % 65)}%` }} />)}</div><div className="stage-floor" /></div>}
    <span className="art-caption">EVENTRA SELECTS <span>VOL. 01</span></span>
  </div>;
}

function Modal({ open, onOpenChange, title, description, children, className = "" }: { open: boolean; onOpenChange: (open: boolean) => void; title: string; description: string; children: React.ReactNode; className?: string }) {
  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="modal-overlay" /><Dialog.Content className={`modal-content ${className}`}>
    <div className="modal-heading"><div><Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description}</Dialog.Description></div><Dialog.Close className="icon-button" aria-label="Close dialog"><X size={20} /></Dialog.Close></div>{children}
  </Dialog.Content></Dialog.Portal></Dialog.Root>;
}

export default function EventraWorkspace() {
  const [view, setView] = useState<"discover" | "saved">("discover");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All artists");
  const [city, setCity] = useState("All cities");
  const [maxPrice, setMaxPrice] = useState("all");
  const [artists, setArtists] = useState<Artist[]>([]);
  const [catalogue, setCatalogue] = useState<Artist[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [reload, setReload] = useState(0);
  const [saved, setSaved] = useState<string[]>([]);
  const [storageReady, setStorageReady] = useState(false);
  const [storageError, setStorageError] = useState("");
  const [selected, setSelected] = useState<Artist | null>(null);
  const [briefOpen, setBriefOpen] = useState(false);
  const [brief, setBrief] = useState<Brief>(EMPTY_BRIEF);
  const [briefSaved, setBriefSaved] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [statusOpen, setStatusOpen] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState("");
  const [aiInput, setAiInput] = useState("");
  const [aiRunning, setAiRunning] = useState(false);
  const [aiStatus, setAiStatus] = useState("");
  const [aiError, setAiError] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const controller = useRef<AbortController | null>(null);
  const assistantRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    try {
      const savedValue: unknown = JSON.parse(localStorage.getItem("eventrahq.saved.v1") || "[]");
      if (Array.isArray(savedValue)) setSaved(savedValue.filter((item): item is string => typeof item === "string"));
      const briefValue: unknown = JSON.parse(localStorage.getItem("eventrahq.brief.v1") || "null");
      if (briefValue && typeof briefValue === "object") {
        const item = briefValue as Record<string, unknown>;
        setBrief(Object.fromEntries(Object.entries(EMPTY_BRIEF).map(([key, value]) => [key, typeof item[key] === "string" ? item[key] : value])) as Brief);
      }
    } catch { setStorageError("Browser storage is unavailable. Your changes will stay in this session."); }
    setStorageReady(true);
    return () => controller.current?.abort();
  }, []);

  useEffect(() => {
    if (!storageReady) return;
    try { localStorage.setItem("eventrahq.saved.v1", JSON.stringify(saved)); }
    catch { setStorageError("Saved artists could not be stored on this browser. They remain available for this session."); }
  }, [saved, storageReady]);

  useEffect(() => {
    const abort = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true); setLoadError("");
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (category !== "All artists") params.set("category", category);
      if (city !== "All cities") params.set("city", city);
      if (maxPrice !== "all") params.set("max_price_paise", maxPrice);
      try {
        const response = await fetch(`/api/v1/artists?${params}`, { signal: abort.signal, cache: "no-store" });
        if (!response.ok) throw new Error(`Catalogue returned ${response.status}.`);
        const data = await response.json();
        if (!Array.isArray(data.items)) throw new Error("Catalogue response was not recognised.");
        setArtists(data.items);
        if (!search.trim() && category === "All artists" && city === "All cities" && maxPrice === "all") setCatalogue(data.items);
      } catch (error) {
        if (abort.signal.aborted) return;
        setLoadError(error instanceof Error ? error.message : "The catalogue could not be reached."); setArtists([]);
      } finally { if (!abort.signal.aborted) setLoading(false); }
    }, 220);
    return () => { clearTimeout(timer); abort.abort(); };
  }, [search, category, city, maxPrice, reload]);

  useEffect(() => {
    const abort = new AbortController();
    fetch("/api/v1/health/ready", { signal: abort.signal, cache: "no-store" }).then(async response => {
      const data = await response.json();
      setHealth(data); setHealthError("");
    }).catch(() => { if (!abort.signal.aborted) setHealthError("The local API is not reachable."); });
    return () => abort.abort();
  }, [reload, statusOpen]);

  function resetFilters() { setSearch(""); setCategory("All artists"); setCity("All cities"); setMaxPrice("all"); }
  function navigate(next: "discover" | "saved") { setView(next); resetFilters(); setNavOpen(false); }
  function toggleSaved(id: string) { setSaved(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]); }
  function saveBrief(event: React.FormEvent) {
    event.preventDefault();
    try { localStorage.setItem("eventrahq.brief.v1", JSON.stringify(brief)); setBriefSaved(true); }
    catch { setStorageError("This event brief is available for this session. Browser storage could not save it."); setBriefSaved(true); }
  }
  function useBrief() {
    const text = [brief.name && `Event: ${brief.name}.`, brief.city && `City: ${brief.city}.`, brief.date && `Date: ${brief.date}.`, brief.budget && `Artist budget: INR ${brief.budget}.`, brief.notes].filter(Boolean).join(" ");
    setAiInput(text.slice(0, 1200)); setBriefOpen(false); setTimeout(() => assistantRef.current?.focus(), 50);
  }

  async function askAssistant() {
    if (!aiInput.trim() || aiRunning) return;
    const abort = new AbortController(); controller.current = abort;
    setAiRunning(true); setAiError(""); setAnswer(null); setAiStatus("Connecting to your local assistant…");
    let gotResult = false;
    try {
      const response = await fetch("/api/v1/assistant/runs", { method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream" }, body: JSON.stringify({ brief: aiInput.trim() }), signal: abort.signal });
      if (!response.ok) {
        let detail = "";
        try {
          const body = await response.json();
          detail = typeof body.detail === "string" ? body.detail
            : Array.isArray(body.detail) ? body.detail.map((item: { msg?: string }) => item.msg || "").filter(Boolean).join(" ")
            : typeof body.message === "string" ? body.message : "";
        } catch { /* status is enough */ }
        throw new Error(detail || `Local assistant returned ${response.status}. Check that Ollama is running and a model is downloaded, then retry.`);
      }
      if (!response.body) throw new Error("The assistant did not open a response stream. Please retry.");
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
      function parseEvent(block: string) {
        let eventName = "message";
        const dataLines: string[] = [];
        block.split("\n").forEach(line => { if (line.startsWith("event:")) eventName = line.slice(6).trim(); if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart()); });
        if (!dataLines.length) return;
        const data = JSON.parse(dataLines.join("\n")); const kind = eventName === "message" ? data.type || data.event || "message" : eventName;
        if (kind === "status") setAiStatus(data.message || "Thinking locally…");
        if (kind === "error") throw new Error(data.message || "The local model could not complete your request. Check its status and retry.");
        if (kind === "result") {
          if (typeof data.message !== "string") throw new Error("The assistant returned an incomplete response. Please retry.");
          gotResult = true; setAnswer({ message: data.message, artist_ids: Array.isArray(data.artist_ids) ? data.artist_ids.filter((id: unknown): id is string => typeof id === "string") : [] }); setAiStatus("Completed on your workstation");
        }
        if (kind === "done" && !gotResult) setAiStatus("Run ended");
      }
      while (true) {
        const chunk = await reader.read();
        buffer = (buffer + decoder.decode(chunk.value, { stream: !chunk.done })).replace(/\r\n/g, "\n");
        let boundary: number;
        while ((boundary = buffer.indexOf("\n\n")) >= 0) { const block = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2); parseEvent(block); }
        if (chunk.done) { if (buffer.trim()) parseEvent(buffer); break; }
      }
      if (!gotResult) throw new Error("The connection ended before a recommendation arrived. Check local model status and retry.");
    } catch (error) {
      if (abort.signal.aborted) setAiStatus("Request cancelled. Your brief is ready to edit.");
      else { setAiError(error instanceof Error ? error.message : "The local assistant is unavailable. Check local services and retry."); setAiStatus(""); }
    } finally { abort.abort(); setAiRunning(false); controller.current = null; }
  }

  const visible = view === "saved" ? artists.filter(artist => saved.includes(artist.id)) : artists;
  const cityOptions = Array.from(new Set([...CITIES, ...catalogue.map(artist => artist.city)]));
  const activeFilters = !!search || category !== "All artists" || city !== "All cities" || maxPrice !== "all";
  const ollama = health?.services?.ollama;
  const localReady = ollama?.status === "ready" || ollama?.status === "ok" || ollama?.status === "healthy";

  const sidebar = <><a href="#main-content" className="brand" onClick={() => navigate("discover")} aria-label="EventraHQ discovery"><img src="/brand/logo-mark.svg" width="38" height="38" alt="" /><span>eventra<span className="brand-hq">HQ</span><small>THE EVENT WORKSPACE</small></span></a>
    <div className="sidebar-section-label">WORKSPACE</div><nav className="main-nav" aria-label="Main navigation">
      <button className={view === "discover" ? "nav-item active" : "nav-item"} onClick={() => navigate("discover")} aria-current={view === "discover" ? "page" : undefined}><Compass size={19} />Discover artists<span className="active-dot" /></button>
      <button className={view === "saved" ? "nav-item active" : "nav-item"} onClick={() => navigate("saved")} aria-current={view === "saved" ? "page" : undefined}><Heart size={18} />Saved artists<span className="nav-count">{saved.length}</span></button>
      <button className="nav-item" onClick={() => { setBriefOpen(true); setBriefSaved(false); setNavOpen(false); }}><SlidersHorizontal size={18} />Event planning<span className="nav-tiny">DRAFT</span></button>
    </nav><div className="sidebar-note"><span className="tiny-spark"><Sparkles size={18} /></span><h3>A little spark.<br />A memorable night.</h3><p>Start with an idea. Find the artists who bring it to life.</p><button onClick={() => { setBriefOpen(true); setBriefSaved(false); setNavOpen(false); }}>Create an event brief<ArrowRight size={15} /></button></div>
    <div className="sidebar-bottom"><button className="system-button" onClick={() => { setStatusOpen(true); setNavOpen(false); }}><span className={`status-dot ${healthError ? "warning" : ""}`} /><span>Local workspace<small>Phase 1 · Development</small></span><Terminal size={15} /></button><div className="user-profile"><span className="avatar">K</span><span>Krishna&apos;s workspace<small>Personal · Local preview</small></span><span className="profile-dot" /></div></div></>;

  return <div className="app-shell"><a href="#main-content" className="skip-link">Skip to main content</a><aside className="desktop-sidebar">{sidebar}</aside>
    <Dialog.Root open={navOpen} onOpenChange={setNavOpen}><Dialog.Portal><Dialog.Overlay className="modal-overlay" /><Dialog.Content className="mobile-sidebar"><Dialog.Title className="sr-only">Workspace navigation</Dialog.Title><Dialog.Description className="sr-only">Discover artists, manage saved artists and plan an event.</Dialog.Description><Dialog.Close className="mobile-nav-close icon-button" aria-label="Close navigation"><X size={20} /></Dialog.Close>{sidebar}</Dialog.Content></Dialog.Portal></Dialog.Root>
    <div className="workspace-main"><header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setNavOpen(true)}><Menu size={21} /></button><span className="workspace-symbol"><Command size={15} /></span><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{view === "discover" ? "Discover" : "Saved artists"}</strong></div><div className="topbar-right"><button className="local-badge" onClick={() => setStatusOpen(true)}><span className="status-dot" />LOCAL PREVIEW</button><span className="topbar-divider" /><span className="topbar-avatar" aria-label="Personal workspace">K</span></div></header>
      <main id="main-content" className="main-content"><div className="page-heading"><div><div className="eyebrow"><span />CURATED TALENT. ENDLESS POSSIBILITIES.</div><h1>{view === "discover" ? <>Find the right <em>energy.</em></> : <>Keep the <em>possibilities.</em></>}</h1><p>{view === "discover" ? "Extraordinary artists for the moments that matter." : "Your shortlist, ready for the next great idea."}</p></div><button className="button button-primary brief-cta" onClick={() => { setBriefOpen(true); setBriefSaved(false); }}><Plus size={18} />Create event brief</button></div>
      {storageError && <div className="notice" role="status">{storageError}</div>}
      <section className="discovery-hero" aria-label="Artist discovery introduction"><div className="hero-copy"><span className="outlined-tag"><span className="status-dot" />THE LOCAL COLLECTION</span><h2>Great events start<br />with a <span>great connection.</span></h2><p>Explore a sample collection of live performers.<br className="desktop-break" /> Your next unforgettable moment starts here.</p><a href="#artist-collection" className="text-link">Meet the artists<ArrowDown size={15} /></a></div><div className="hero-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="hero-glow" /><div className="hero-orbit-label"><span /> LIVE IN YOUR ELEMENT</div><div className="hero-wave">{Array.from({ length: 27 }, (_, i) => <span key={i} style={{ height: `${24 + ((i * 23 + 9) % 96)}px` }} />)}</div><span className="floating-star star-one">✦</span><span className="floating-star star-two">✧</span><div className="hero-caption"><AudioLines size={16} /> A different kind of discovery</div></div></section>
      <section className="collection-section" id="artist-collection" aria-labelledby="collection-title"><div className="collection-top"><div><h2 id="collection-title">{view === "saved" ? "Your saved artists" : "Explore the collection"}<span className="sample-pill">SAMPLE CATALOGUE</span></h2><p>Find a sound that feels like your event.</p></div><span className="collection-count" aria-live="polite">{loading ? "Finding artists…" : `${visible.length} artist${visible.length === 1 ? "" : "s"}`}</span></div>
      <div className="filter-bar"><div className="search-field"><Search size={18} /><label className="sr-only" htmlFor="artist-search">Search artists, sounds or styles</label><input id="artist-search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search artists, sounds or styles…" autoComplete="off" />{search && <button aria-label="Clear search" className="clear-search" onClick={() => setSearch("")}><X size={16} /></button>}</div><label className="select-field"><MapPin size={17} /><span className="sr-only">Filter by city</span><select aria-label="Filter by city" value={city} onChange={event => setCity(event.target.value)}>{cityOptions.map(value => <option key={value}>{value}</option>)}</select><ChevronDown size={15} /></label><label className="select-field budget-filter"><SlidersHorizontal size={17} /><span className="sr-only">Maximum artist fee</span><select aria-label="Maximum artist fee" value={maxPrice} onChange={event => setMaxPrice(event.target.value)}><option value="all">Any budget</option><option value="2500000">Up to ₹25,000</option><option value="5000000">Up to ₹50,000</option><option value="10000000">Up to ₹1,00,000</option></select><ChevronDown size={15} /></label></div>
      <div className="category-row" role="group" aria-label="Filter artist category">{CATEGORIES.map((value, index) => <button key={value} className={`category-pill ${category === value ? "selected" : ""}`} onClick={() => setCategory(value)} aria-pressed={category === value}>{index === 0 ? <Compass size={15} /> : index === 1 ? <AudioLines size={16} /> : index === 2 ? <Radio size={16} /> : index === 3 ? <Mic2 size={15} /> : <Music2 size={15} />}{value === "Live band" ? "Live bands" : value === "DJ" ? "DJs" : value === "Vocalist" ? "Vocalists" : value}{index === 0 && <span className="pill-spark">✦</span>}</button>)}{activeFilters && <button className="reset-filters" onClick={resetFilters}>Reset filters<X size={13} /></button>}</div>
      {loading ? <div className="artist-grid" aria-label="Loading catalogue" aria-busy="true">{Array.from({ length: 8 }, (_, i) => <div className="skeleton-card" key={i}><div /><span /><span /><span /></div>)}</div> : loadError ? <div className="empty-state error-state" role="alert"><Terminal size={32} /><h3>The local catalogue is out of reach.</h3><p>{loadError} Start the API and database services, then try again.</p><button className="button button-primary" onClick={() => setReload(value => value + 1)}>Retry connection<ArrowRight size={16} /></button></div> : visible.length === 0 ? <div className="empty-state"><Search size={32} /><h3>{view === "saved" && !activeFilters ? "Your next favourite is waiting." : "A different search could be the one."}</h3><p>{view === "saved" && !activeFilters ? "Tap the heart on an artist to keep them in your shortlist." : "Try another city, a wider budget, or fewer search terms."}</p><button className="button button-secondary" onClick={view === "saved" && !activeFilters ? () => navigate("discover") : resetFilters}>{view === "saved" && !activeFilters ? "Discover artists" : "Clear all filters"}<ArrowRight size={16} /></button></div> : <div className="artist-grid">{visible.map(artist => <article className="artist-card" key={artist.id}><div className="card-art-wrap"><ArtistArtwork artist={artist} /><span className="category-label">{artist.category}</span><button className={`save-button ${saved.includes(artist.id) ? "is-saved" : ""}`} onClick={() => toggleSaved(artist.id)} aria-label={`${saved.includes(artist.id) ? "Remove" : "Save"} ${artist.name}${saved.includes(artist.id) ? " from saved artists" : ""}`} aria-pressed={saved.includes(artist.id)}><Heart size={18} fill={saved.includes(artist.id) ? "currentColor" : "none"} /></button></div><div className="artist-info"><div className="artist-name-row"><h3>{artist.name}</h3><span className="rating"><Star size={12} fill="currentColor" />{artist.rating.toFixed(1)}</span></div><p className="artist-tagline">{artist.tagline}</p><div className="artist-location"><MapPin size={12} />{artist.city}<span>·</span><span>Sample artist</span></div><div className="artist-card-bottom"><div><small>ILLUSTRATIVE FEE</small><strong>{money(artist.price_paise)}<span> / event</span></strong></div><button className="card-view" onClick={() => setSelected(artist)} aria-label={`View ${artist.name}`}><ArrowRight size={18} /></button></div></div></article>)}</div>}
      <p className="catalogue-disclaimer"><span className="disclaimer-mark">i</span> A curated demo: artist profiles, ratings, fees and availability are synthetic. No live booking or real availability.</p></section>
      <section className="assistant-section" aria-labelledby="assistant-title"><div className="assistant-intro"><span className="assistant-icon"><WandSparkles size={23} /></span><div className="eyebrow">A LITTLE HELP FINDING YOUR SOUND</div><h2 id="assistant-title">Your idea. A local<br /><span>AI-powered shortlist.</span></h2><p>Describe the vibe, the city, the occasion.<br />Let your self-hosted assistant connect the dots.</p><button className="assistant-status" onClick={() => setStatusOpen(true)}><span className={`status-dot ${!localReady ? "warning" : ""}`} />{localReady ? "Local model connected" : "Check local model status"}<ArrowRight size={12} /></button></div><div className="assistant-workspace"><label htmlFor="assistant-brief">What are you planning?<span>YOUR EVENT BRIEF</span></label><textarea id="assistant-brief" ref={assistantRef} value={aiInput} onChange={event => setAiInput(event.target.value)} maxLength={1200} placeholder="An intimate rooftop celebration in Bengaluru, with soulful live music for 60 guests. Budget around ₹50,000…" rows={4} disabled={aiRunning} /><div className="assistant-actions"><span><span className="status-dot" />Runs on your workstation</span>{aiRunning ? <button className="button button-secondary" onClick={() => controller.current?.abort()}><Square size={13} />Cancel</button> : <button className="button button-primary" onClick={askAssistant} disabled={!aiInput.trim()}><Sparkles size={15} />Find my artists<ArrowRight size={15} /></button>}</div>{aiStatus && <p className={`ai-status ${aiRunning ? "is-running" : ""}`} role="status">{aiRunning && <span className="loading-ring" />}{aiStatus}</p>}{aiError && <div className="ai-error" role="alert"><p>{aiError}</p><button onClick={askAssistant} disabled={aiRunning || !aiInput.trim()}>Retry recommendation<ArrowRight size={14} /></button></div>}{answer && <div className="ai-answer"><div><Sparkles size={14} /><strong>Your local recommendation</strong></div><p>{answer.message}</p>{answer.artist_ids.length > 0 && <ul aria-label="Recommended artists">{answer.artist_ids.map(id => { const artist = catalogue.find(item => item.id === id) || artists.find(item => item.id === id); return <li key={id}>{artist ? <button onClick={() => setSelected(artist)}>{artist.name}<ArrowRight size={12} /></button> : <span>Artist reference: {id}</span>}</li>; })}</ul>}</div>}</div></section>
      <footer className="page-footer"><span><img src="/brand/logo-mark.svg" width="22" height="22" alt="" />Made for memorable moments.</span><span>Local preview · No authentication · No real transactions</span></footer></main>
    </div>
    <Modal open={selected !== null} onOpenChange={open => { if (!open) setSelected(null); }} title={selected?.name || "Artist details"} description="Sample artist profile · illustrative catalogue" className="artist-modal">{selected && <><ArtistArtwork artist={selected} large /><div className="detail-meta"><span className="outlined-tag">{selected.category}</span><span><MapPin size={14} />{selected.city}</span><span className="rating"><Star size={13} fill="currentColor" />{selected.rating.toFixed(1)} <span>({selected.review_count} sample reviews)</span></span></div><h3 className="detail-tagline">{selected.tagline}</h3><p className="detail-description">{selected.description}</p><div className="artist-tags">{selected.tags.map(tag => <span key={tag}>{tag}</span>)}</div><div className="detail-fee"><span>Illustrative event fee<strong>{money(selected.price_paise)}</strong></span><button className="button button-primary" onClick={() => toggleSaved(selected.id)}><Heart size={16} fill={saved.includes(selected.id) ? "currentColor" : "none"} />{saved.includes(selected.id) ? "Saved to shortlist" : "Save artist"}</button></div><p className="dialog-fineprint">This is a fictional profile. Fees, reviews and availability are examples. Booking is not enabled in the local preview.</p></>}</Modal>
    <Modal open={briefOpen} onOpenChange={setBriefOpen} title="Every great event starts with an idea." description="Shape your event brief. Drafts are stored only in this browser."><form onSubmit={saveBrief} className="brief-form"><label>Event name<input value={brief.name} maxLength={120} onChange={event => { setBrief({ ...brief, name: event.target.value }); setBriefSaved(false); }} placeholder="e.g. Rooftop under the stars" /></label><div className="form-pair"><label>City<select value={brief.city} onChange={event => { setBrief({ ...brief, city: event.target.value }); setBriefSaved(false); }}>{cityOptions.slice(1).map(value => <option key={value}>{value}</option>)}</select></label><label>Event date<input type="date" value={brief.date} onChange={event => { setBrief({ ...brief, date: event.target.value }); setBriefSaved(false); }} /></label></div><label>Artist budget (INR)<input type="number" min="0" max="100000000" step="1000" value={brief.budget} onChange={event => { setBrief({ ...brief, budget: event.target.value }); setBriefSaved(false); }} placeholder="50000" /></label><label>The occasion and the vibe<textarea value={brief.notes} maxLength={800} onChange={event => { setBrief({ ...brief, notes: event.target.value }); setBriefSaved(false); }} placeholder="Tell us about your guests, the atmosphere and the sound you have in mind…" rows={4} /></label>{briefSaved && <p className="saved-notice" role="status"><Check size={16} />Draft saved for this browser session.</p>}<div className="form-actions"><button type="submit" className="button button-secondary">{briefSaved ? <Check size={16} /> : <Plus size={16} />}Save draft</button><button type="button" className="button button-primary" onClick={useBrief}>Use with local AI<ArrowRight size={16} /></button></div></form></Modal>
    <Modal open={statusOpen} onOpenChange={setStatusOpen} title="Your local workspace" description="Phase 1 service readiness. Everything runs on your own machine."><div className="service-list">{healthError && <p className="ai-error">{healthError} Start the local stack and retry.</p>}{health?.services && Object.entries(health.services).map(([name, service]) => <div className="service-item" key={name}><div><span className={`status-dot ${!["ok", "healthy", "ready"].includes(service.status) ? "warning" : ""}`} /><strong>{name === "ollama" ? "Ollama · Local AI" : name === "database" ? "Local database" : name}</strong></div><span className="service-status">{service.status}</span>{service.message && <p>{service.message}</p>}</div>)}{!health && !healthError && <p className="muted">Checking local services…</p>}<p className="dialog-fineprint">This preview uses a synthetic artist catalogue. There is no account login, live booking, cloud inference or payment processing.</p><button className="button button-secondary" onClick={() => setReload(value => value + 1)}>Refresh status<ArrowRight size={15} /></button></div></Modal>
  </div>;
}

