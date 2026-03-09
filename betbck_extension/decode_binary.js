// Copy-paste this entire block into the browser console on plive.becoms.co

// Step 1: Load pako (gzip library)
(async function() {
  if (!window.pako) {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js';
    document.head.appendChild(script);
    await new Promise(resolve => script.onload = resolve);
  }
  
  // Your binary base64 string
  const b64 = `H4sIAAAAAAACA43Qz2rDMAwG8HfxuSSSLMtWznuLsYP/KKyQ0b_limitlg1Hy7nMOY+2pBZ9k/77P9tUdv16O8+ym9fNiB3fOP8spNze9Xt3p7Cb3aeclV3P71vreB2MdP0aE8TTSCH38nZeLuYkHwu3wDMJ/hAOmSCLPQH/bps+JuypgIHgECWOXTBribR/CEPgBDfvrhnDLZHhY+KfufwUk+bS9Hdx6dNPV7aezBUavxpkYivoQsTXQGLNmTpmCKDMjSYQ5NZPoSxIVyoStRuWev8x7EEgNrXCVIJ6LzaAhi1IsyWZVnwg1p+qpUNJi1rgUMFbiyNUKlh609ktG6SskTKC4bb8UucouSAIAAA==`;
  
  // Decode base64 -> binary
  function b64ToBytes(b64) {
    const bin = atob(b64.replace(/\s/g, ''));
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
  }
  
  try {
    const bytes = b64ToBytes(b64);
    const inflated = pako.inflate(bytes, { to: 'string' });
    const json = JSON.parse(inflated);
    
    console.log('✅ DECODED ODDS DATA:');
    console.log(JSON.stringify(json, null, 2));
    
    // Also save to window so you can inspect it
    window.lastDecodedOdds = json;
    console.log('💾 Saved to window.lastDecodedOdds');
    
  } catch (e) {
    console.error('❌ Error decoding:',锅 e);
  }
})();

