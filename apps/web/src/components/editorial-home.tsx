import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowDown, ArrowRight, ArrowUpRight, Music2, Search, MapPin, CalendarDays } from "lucide-react";

const disciplines = [
  { name: "Live bands", value: "Live band", detail: "A room. A rhythm. A shared moment.", image: "live-band.jpg" },
  { name: "DJs", value: "DJ", detail: "The soundtrack to a night of your own.", image: "dj-decks.jpg" },
  { name: "Singers", value: "Vocalist", detail: "A voice that makes the occasion.", image: "live-vocals.jpg" },
  { name: "Instrumentalists", value: "Instrumental", detail: "Atmosphere, in its purest form.", image: "classical-violin.jpg" },
];

export default function EditorialHome({ artists, cities, occasions }: { artists: ReactNode; cities: string[]; occasions: string[] }) {
  return <div className="editorial-home">
    <section className="hero">
      <div className="container hero-stage">
        <div className="hero-copy"><span className="eyebrow">EVENTRA / THE ART OF COMING TOGETHER</span>
          <h1>Some nights<br /><em>stay with you.</em></h1>
          <p>Extraordinary artists. Unforgettable events.<br />Find the people who give your occasion its own sound.</p>
          <div className="hero-cta"><Link href="/artists" className="button cream">Explore artists <ArrowUpRight size={18} /></Link><Link href="/plan" className="text-link">Plan your event <ArrowRight size={17} /></Link></div>
          <a href="#discover" className="hero-scroll"><ArrowDown size={16} /> A world of live performance</a>
        </div>
        <figure className="hero-visual"><img src="/images/acoustic-sunset.jpg" alt="Illustrative acoustic performance in the warm evening light" width="1200" height="1800" fetchPriority="high" /><figcaption><span>THE FEELING OF BEING THERE</span><span>Illustrative performance photography</span></figcaption></figure>
        <div className="hero-edition"><span>LIVE MUSIC. REAL CONNECTION.</span><span>BANDS / DJS / VOICES / STRINGS</span></div>
      </div>
    </section>

    <section id="discover" className="container search-wrap" aria-label="Find an artist">
      <div className="search-heading"><span className="eyebrow">BEGIN WITH AN OCCASION</span><p>What does your<br /><em>next moment sound like?</em></p></div>
      <form action="/artists" className="hero-search">
        <label><span><Search size={14} /> THE SOUND</span><input name="search" placeholder="Artist, genre or inspiration" aria-label="Search artists, sounds or styles" /></label>
        <label><span><MapPin size={14} /> THE PLACE</span><select name="city" aria-label="Event location"><option value="">All cities</option>{cities.map(city => <option key={city}>{city}</option>)}</select></label>
        <label><span><CalendarDays size={14} /> THE OCCASION</span><select name="event_type" aria-label="Event type"><option value="">Any occasion</option>{occasions.map(occasion => <option key={occasion}>{occasion}</option>)}</select></label>
        <button className="button" type="submit">Find artists <ArrowUpRight size={18} /></button>
      </form>
    </section>

    <section className="container section discipline-section">
      <div className="section-heading"><div><span className="eyebrow">01 / FIND YOUR SOUND</span><h2>A different kind<br />of <em>presence.</em></h2></div><p>From the first note to the last dance.<br />Explore the talent behind the feeling.</p></div>
      <div className="discipline-grid">{disciplines.map((item, index) => <Link className="discipline" key={item.value} href={`/artists?category=${encodeURIComponent(item.value)}`}><div className="discipline-image"><img src={`/images/${item.image}`} alt={`Illustrative ${item.name.toLowerCase()} performance`} width="600" height="700" loading="lazy" /><span className="discipline-number">0{index + 1}</span><span className="discipline-arrow"><ArrowUpRight size={24} /></span></div><div className="discipline-caption"><h3>{item.name}</h3><p>{item.detail}</p></div></Link>)}</div>
      <p className="image-disclosure">Performance photographs illustrate each discipline; they are not artist endorsements.</p>
    </section>

    <section className="artists-section section"><div className="container"><div className="section-heading"><div><span className="eyebrow">02 / THE PEOPLE BEHIND THE MOMENT</span><h2>Meet your next<br /><em>great memory.</em></h2></div><Link className="text-link" href="/artists">Explore the catalogue <ArrowUpRight size={18} /></Link></div>{artists}</div></section>

    <section className="container section occasion-story"><div className="occasion-image"><img src="/images/classical-violin.jpg" alt="Illustrative ensemble of violinists performing together" width="1200" height="884" loading="lazy" /><span>THE DETAILS MAKE THE DIFFERENCE</span></div><div className="occasion-copy"><span className="eyebrow">03 / FROM IDEA TO OCCASION</span><h2>Beautiful things<br />begin with<br /><em>a conversation.</em></h2><p>Your occasion is personal. The planning should be, too. Share the details, speak with an artist, and agree a quote that brings your vision together.</p><ol className="journey-list"><li><span>01</span><div><h3>Find your people</h3><p>Explore by sound, city and budget. Keep a shortlist.</p></div></li><li><span>02</span><div><h3>Make it personal</h3><p>Share your brief and agree the details with your artist.</p></div></li><li><span>03</span><div><h3>Set the date</h3><p>Accept a quote, then complete payment. Your booking is confirmed once payment is verified.</p></div></li></ol><Link href="/plan" className="text-link">Start your event brief <ArrowUpRight size={18} /></Link></div></section>

    <section className="city-section"><div className="container city-layout"><div><span className="eyebrow">CLOSER TO YOUR OCCASION</span><h2>Every city.<br /><em>A different rhythm.</em></h2><p>Discover artists by where your story unfolds.</p></div><div className="city-links">{cities.map((city, i) => <Link href={`/artists?city=${encodeURIComponent(city)}`} key={city}><span className="city-number">0{i + 1}</span><span>{city}</span><ArrowUpRight size={20} /></Link>)}</div></div></section>

    <section className="container section inspiration"><span className="eyebrow"><Music2 size={15} /> A LITTLE INSPIRATION</span><h2>You have a feeling.<br /><em>Let’s find its sound.</em></h2><div><p>Tell our planning assistant about the occasion. Explore suggestions from the catalogue, then make the choice your own.</p><Link href="/plan#assistant" className="button outline">Explore with the assistant <ArrowUpRight size={18} /></Link><small>Recommendations, never automatic bookings.</small></div></section>
    <section className="artist-invite"><div className="container"><span className="eyebrow">FOR THE ARTISTS</span><h2>The next great occasion<br />could have <em>your name on it.</em></h2><Link href="/join" className="button cream">Become an artist <ArrowUpRight size={18} /></Link></div></section>
  </div>;
}

