document.getElementById("nearme")?.addEventListener("click", () => {
  navigator.geolocation.getCurrentPosition(p => {
    const f = document.getElementById("searchform");
    f.lat.value = p.coords.latitude.toFixed(5); f.lng.value = p.coords.longitude.toFixed(5); f.submit();
  });
});
