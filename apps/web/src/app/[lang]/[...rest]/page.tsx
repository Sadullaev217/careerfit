import { notFound } from 'next/navigation';

// Sends unknown addresses to this language's own not-found page.
export default function UnknownRoute() {
  notFound();
}
