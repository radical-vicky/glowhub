const start = document.getElementById("cam-start"), snap = document.getElementById("cam-snap");
const video = document.getElementById("cam-video"), canvas = document.getElementById("cam-canvas");
start?.addEventListener("click", async () => {
  try {
    video.srcObject = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
    video.hidden = false; snap.hidden = false; start.hidden = true;
  } catch { alert("Camera unavailable. Upload a selfie photo instead."); }
});
snap?.addEventListener("click", () => {
  canvas.width = video.videoWidth; canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  canvas.toBlob(b => {
    const dt = new DataTransfer(); dt.items.add(new File([b], "selfie.jpg", { type: "image/jpeg" }));
    document.getElementById("id_selfie").files = dt.files;
    video.srcObject.getTracks().forEach(t => t.stop()); video.hidden = true; snap.hidden = true;
    canvas.hidden = false;
  }, "image/jpeg", 0.9);
});
