"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, ArrowUpRight, CalendarDays, CheckCheck, ChevronLeft, ChevronRight, Heart, MapPin, MessageCircle, Music2, Plus, Search, Sparkles, Users } from "lucide-react";
import { api, money, Notice } from "./marketplace";

type RecordRow = { id: string; [key: string]: unknown };
type EventRow = RecordRow & { title: string; city: string; starts_at: string; ends_at: string; event_type: string; budget_paise: number; guest_count: number; notes: string };
type Records<T> = { items: T[] };
const text = (row: RecordRow, field: string) => String(row[field] ?? "");
const displayDate = (value: string, options?: Intl.DateTimeFormatOptions) => new Date(value).toLocaleDateString("en-IN", options ?? { day: "numeric", month: "short", year: "numeric" });
const dayKey = (value: Date) => `${value.getFullYear()}-${value.getMonth()}-${value.getDate()}`;
const artistSearch = (event: EventRow) => `/artists?${new URLSearchParams({ city: event.city, event_type: event.event_type })}`;

function useRecords<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    api<T>(path).then(value => { if (active) setData(value); }).catch(reason => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [path, attempt]);
  return { data, error, retry: () => { setError(""); setData(null); setAttempt(value => value + 1); } };
}

function LoadFailure({ message, retry }: { message: string; retry: () => void }) {
  return <Notice error>{message} <button className="text-button" onClick={retry}>Try again</button></Notice>;
}

export function WorkspaceWelcome() {
  return <>
    <section className="workspace-banner guest-banner">
      <div><span className="eyebrow">A LITTLE PLANNING. A LOT TO LOOK FORWARD TO.</span><h2>Your next occasion,<br /><em>all in one place.</em></h2><p>Find your artist, shape the details and keep every conversation together.</p><Link href="/plan" className="button cream">Start an event brief <ArrowRight size={17} /></Link></div>
      <div className="banner-art" aria-hidden="true"><span className="art-orbit" /><Music2 /><span className="art-caption">MAKE IT MEMORABLE</span></div>
    </section>
    <div className="workspace-start-grid">
      {[{ Icon: CalendarDays, title: "Bring an idea", body: "Save an event brief with your date, budget and the sound you have in mind.", href: "/plan", action: "Plan your event" }, { Icon: Heart, title: "Find your people", body: "Explore bands, DJs and performers. Keep the artists you love on your shortlist.", href: "/artists", action: "Explore artists" }, { Icon: MessageCircle, title: "Make a connection", body: "Sign in to contact artists, discuss a quote and follow your booking.", href: "/login", action: "Create your account" }].map(({ Icon, title, body, href, action }, i) => <article className="workspace-start-card" key={title}><span className="start-number">0{i + 1}</span><Icon size={24} /><h3>{title}</h3><p>{body}</p><Link className="text-link" href={href}>{action}<ArrowUpRight size={16} /></Link></article>)}
    </div>
  </>;
}

export function AccountOverview({ navigate }: { navigate: (tab: string) => void }) {
  const events = useRecords<Records<EventRow>>("/events");
  const bookings = useRecords<Records<RecordRow>>("/bookings");
  const inquiries = useRecords<Records<RecordRow>>("/inquiries");
  const notifications = useRecords<Records<RecordRow>>("/notifications");
  const profile = useRecords<{ profile: RecordRow }>("/me");
  const upcoming = events.data?.items.filter(event => new Date(event.ends_at).getTime() >= Date.now()).sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at));
  const confirmed = bookings.data?.items.filter(booking => booking.status === "confirmed");
  const pending = bookings.data?.items.filter(booking => booking.status === "pending_payment" && Date.parse(text(booking, "expires_at")) > Date.now());
  const name = profile.data ? text(profile.data.profile, "display_name").trim().split(/\s+/)[0] : "";
  return <div className="overview">
    <section className="workspace-banner">
      <div><span className="eyebrow">YOUR OCCASIONS, ORCHESTRATED</span><h2>{name ? `Welcome back, ${name}.` : "Good things are coming."}<br /><em>Let’s set the scene.</em></h2><p>A place for your plans, your people and everything coming together.</p><Link className="button cream" href="/plan"><Plus size={17} /> Create an event</Link></div>
      <div className="banner-art" aria-hidden="true"><span className="art-orbit" /><Music2 /><span className="art-caption">MAKE IT MEMORABLE</span></div>
    </section>
    <div className="workspace-metrics">
      {[{ label: "Upcoming events", value: upcoming?.length, error: events.error, Icon: CalendarDays, tab: "events", note: "Your next occasions" }, { label: "Conversations", value: inquiries.data?.items.length, error: inquiries.error, Icon: MessageCircle, tab: "inbox", note: "Keep the details together" }, { label: "Confirmed bookings", value: confirmed?.length, error: bookings.error, Icon: CheckCheck, tab: "bookings", note: "Your confirmed reservations" }].map(({ label, value, error, Icon, tab, note }) => <button className="workspace-metric" key={label} onClick={() => navigate(tab)}><span className="metric-top"><span>{label}</span><Icon size={19} /></span><strong>{error ? "—" : value ?? "…"}</strong><span className="metric-bottom">{error ? "Unable to load" : note}<ArrowUpRight size={16} /></span></button>)}
    </div>
    <div className="overview-columns">
      <section className="workspace-panel"><div className="panel-heading"><div><span className="eyebrow">ON THE HORIZON</span><h2>Upcoming events</h2></div><button className="text-button" onClick={() => navigate("events")}>View all <ArrowRight size={16} /></button></div>
        {events.error ? <LoadFailure message={events.error} retry={events.retry} /> : !events.data ? <p className="workspace-loading" role="status">Loading your events…</p> : !upcoming?.length ? <div className="workspace-empty"><span className="empty-symbol"><CalendarDays size={28} /></span><h3>Your next story starts here.</h3><p>Create an event brief, then find an artist who feels right.</p><Link className="button outline" href="/plan">Plan your first event <Plus size={16} /></Link></div> : <div className="upcoming-list">{upcoming.slice(0, 3).map(event => <article key={event.id} className="upcoming-event"><div className="event-date-tile"><span>{displayDate(event.starts_at, { month: "short" })}</span><strong>{new Date(event.starts_at).getDate()}</strong></div><div><span className="eyebrow">{event.event_type}</span><h3>{event.title}</h3><p><MapPin size={13} />{event.city}<span>·</span>{event.guest_count} guests</p><Link className="text-link" href={artistSearch(event)}>Find an artist <ArrowRight size={15} /></Link></div></article>)}</div>}
      </section>
      <aside className="workspace-panel"><div className="panel-heading"><div><span className="eyebrow">THE LATEST</span><h2>Your activity</h2></div><span className="activity-dot" aria-hidden="true" /></div>
        {bookings.error && <LoadFailure message={bookings.error} retry={bookings.retry} />}
        {!!pending?.length && <button className="payment-reminder" onClick={() => navigate("bookings")}><CalendarDays size={18} /><span><strong>{pending.length} booking{pending.length === 1 ? "" : "s"} awaiting payment</strong><small>Review your hold before it expires.</small></span><ArrowRight size={16} /></button>}
        {notifications.error ? <LoadFailure message={notifications.error} retry={notifications.retry} /> : !notifications.data ? <p className="workspace-loading" role="status">Loading activity…</p> : !notifications.data.items.length ? <div className="activity-empty"><MessageCircle size={26} /><h3>All quiet for now.</h3><p>Updates about your enquiries and bookings will appear here.</p></div> : <div className="activity-list">{notifications.data.items.slice(0, 4).map(item => <button key={item.id} onClick={() => navigate("notifications")}><span className={`activity-mark ${item.read_at ? "read" : ""}`} /><span><strong>{text(item, "title")}</strong><small>{displayDate(text(item, "created_at"))}</small></span><ArrowUpRight size={14} /></button>)}</div>}
        {inquiries.error && <LoadFailure message={inquiries.error} retry={inquiries.retry} />}
        <Link className="workspace-shortlist" href="/saved"><Heart size={18} /><span>Your artist shortlist<small>Keep your favourites close.</small></span><ArrowRight size={16} /></Link>
      </aside>
    </div>
    <Link className="workspace-discovery" href="/artists"><span className="discovery-symbol"><Sparkles size={24} /></span><div><h3>The right artist changes everything.</h3><p>Explore live bands, DJs, singers and instrumentalists.</p></div><span className="text-link">Discover your sound <ArrowUpRight size={18} /></span></Link>
  </div>;
}

export function EventCollection() {
  const { data, error, retry } = useRecords<Records<EventRow>>("/events");
  const [filter, setFilter] = useState("upcoming");
  const [search, setSearch] = useState("");
  const filtered = data?.items.filter(event => (filter === "all" || (Date.parse(event.ends_at) >= Date.now()) === (filter === "upcoming")) && `${event.title} ${event.city}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));
  return <>
    <div className="workspace-section-heading"><div><h2>Good times in the making.</h2><p>Every occasion starts with a few thoughtful details.</p></div><Link className="button" href="/plan"><Plus size={17} />Create event</Link></div>
    <div className="events-toolbar"><div className="segmented-controls" aria-label="Filter events">{["upcoming", "past", "all"].map(item => <button key={item} aria-pressed={filter === item} onClick={() => setFilter(item)}>{item === "all" ? "All events" : item[0].toUpperCase() + item.slice(1)}</button>)}</div><label className="event-search"><Search size={17} /><input aria-label="Search your events" placeholder="Search your events" value={search} onChange={event => setSearch(event.target.value)} /></label></div>
    {error ? <LoadFailure message={error} retry={retry} /> : !data ? <p className="workspace-loading" role="status">Loading your events…</p> : !filtered?.length ? <div className="workspace-empty workspace-panel"><span className="empty-symbol"><CalendarDays size={28} /></span><h3>{data.items.length ? "No events in this view." : "Make room for a great occasion."}</h3><p>{data.items.length ? "Try a different search or view all your events." : "Your saved events will appear here. Start with a date and an idea."}</p>{data.items.length ? <button className="button outline" onClick={() => { setFilter("all"); setSearch(""); }}>Show all events</button> : <Link className="button" href="/plan">Create your first event <Plus size={17} /></Link>}</div> : <div className="event-collection">{filtered.map(event => <article className="event-card" key={event.id}><div className="event-card-top"><span className="event-type-icon"><Music2 size={25} /></span><span className="badge">{Date.parse(event.ends_at) >= Date.now() ? "Upcoming" : "Past event"}</span></div><span className="eyebrow">{event.event_type}</span><h3>{event.title}</h3><div className="event-facts"><span><CalendarDays size={15} />{displayDate(event.starts_at)}</span><span><MapPin size={15} />{event.city}</span><span><Users size={15} />{event.guest_count} guests</span></div>{event.notes && <p className="event-notes">{event.notes}</p>}<div className="event-card-bottom"><div><small>Artist budget</small><strong>{money(event.budget_paise)}</strong></div><Link className="text-link" href={artistSearch(event)}>Explore artists <ArrowUpRight size={17} /></Link></div></article>)}</div>}
  </>;
}

export function EventCalendar() {
  const { data, error, retry } = useRecords<Records<EventRow>>("/events");
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [selected, setSelected] = useState(() => dayKey(new Date()));
  const first = new Date(month.getFullYear(), month.getMonth(), 1).getDay();
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const matching = data?.items.filter(event => dayKey(new Date(event.starts_at)) === selected) ?? [];
  const move = (offset: number) => { const next = new Date(month.getFullYear(), month.getMonth() + offset, 1); setMonth(next); setSelected(dayKey(next)); };
  return <><div className="workspace-section-heading"><div><h2>Something to look forward to.</h2><p>Your events, by their start date in your local time.</p></div><Link href="/plan" className="button"><Plus size={17} />Create event</Link></div>{error ? <LoadFailure message={error} retry={retry} /> : !data ? <p role="status">Loading your calendar…</p> : <div className="calendar-layout"><section className="workspace-panel"><div className="calendar-heading"><h3 aria-live="polite">{month.toLocaleDateString("en-IN", { month: "long", year: "numeric" })}</h3><div><button className="icon-button" aria-label="Previous month" onClick={() => move(-1)}><ChevronLeft size={20} /></button><button className="icon-button" aria-label="Next month" onClick={() => move(1)}><ChevronRight size={20} /></button></div></div><div className="calendar-grid">{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map(day => <span className="weekday" key={day}>{day}</span>)}{Array.from({ length: first }, (_, i) => <span key={`blank-${i}`} />)}{Array.from({ length: days }, (_, i) => { const day = new Date(month.getFullYear(), month.getMonth(), i + 1); const key = dayKey(day); const count = data.items.filter(event => dayKey(new Date(event.starts_at)) === key).length; return <button key={key} aria-pressed={key === selected} className={key === dayKey(new Date()) ? "today" : ""} aria-label={`${day.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}, ${count} events`} onClick={() => setSelected(key)}>{i + 1}{count > 0 && <span className="calendar-dot" />}</button>; })}</div><p className="calendar-legend"><span className="calendar-dot" /> An event starts on this day</p></section><section className="workspace-panel calendar-agenda"><span className="eyebrow">SELECTED DAY</span><h3>Your day at a glance</h3>{!matching.length ? <div className="activity-empty"><CalendarDays size={28} /><p>No events start on this day.</p><Link href="/plan" className="text-link">Plan something <Plus size={16} /></Link></div> : matching.map(event => <article key={event.id}><span className="eyebrow">{event.event_type}</span><h3>{event.title}</h3><p>{event.city} · {new Date(event.starts_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}</p><Link href={artistSearch(event)} className="text-link">Explore artists <ArrowRight size={15} /></Link></article>)}</section></div>}</>;
}
