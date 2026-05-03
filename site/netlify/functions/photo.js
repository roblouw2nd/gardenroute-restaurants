/**
 * Netlify Function: /api/photo?name=places/PLACE_ID/photos/PHOTO_REF
 *
 * Proxies Google Places photo requests server-side so the API key is never
 * exposed in the browser. Returns the image binary directly.
 *
 * Set GOOGLE_PLACES_API_KEY in Netlify → Site settings → Environment variables.
 */

export default async function handler(req, context) {
  const url   = new URL(req.url);
  const name  = url.searchParams.get('name');   // e.g. "places/ChIJ.../photos/Ab43m..."
  const width = url.searchParams.get('w') || '800';

  if (!name || !name.startsWith('places/')) {
    return new Response('Bad request', { status: 400 });
  }

  const apiKey = process.env.GOOGLE_PLACES_API_KEY;
  if (!apiKey) {
    return new Response('Server misconfiguration: missing API key', { status: 500 });
  }

  const googleUrl =
    `https://places.googleapis.com/v1/${name}/media` +
    `?maxWidthPx=${width}&skipHttpRedirect=true&key=${apiKey}`;

  try {
    const resp = await fetch(googleUrl);
    if (!resp.ok) {
      return new Response('Photo not found', { status: resp.status });
    }

    const data = await resp.json();
    const photoUri = data.photoUri;

    if (!photoUri) {
      return new Response('No photoUri in response', { status: 502 });
    }

    // Fetch the actual image and stream it back
    const imgResp = await fetch(photoUri);
    const imgBuf  = await imgResp.arrayBuffer();
    const ct      = imgResp.headers.get('content-type') || 'image/jpeg';

    return new Response(imgBuf, {
      status: 200,
      headers: {
        'Content-Type':  ct,
        'Cache-Control': 'public, max-age=2592000, immutable', // cache 30 days
        'Access-Control-Allow-Origin': '*',
      },
    });
  } catch (err) {
    console.error('Photo proxy error:', err);
    return new Response('Proxy error', { status: 502 });
  }
}

export const config = { path: '/api/photo' };
