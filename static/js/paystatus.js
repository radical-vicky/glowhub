setInterval(async () => {
  const r = await fetch("?json=1"); const d = await r.json();
  if (d.status !== "PENDING_PAYMENT") location.reload();
}, 3000);
