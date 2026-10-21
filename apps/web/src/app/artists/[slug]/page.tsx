import { ArtistProfile } from "../../../components/marketplace";
export default async function Page({ params }: { params: Promise<{ slug: string }> }) { return <ArtistProfile slug={(await params).slug} />; }
