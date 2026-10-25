(function () {
  // Poll a running test run and reload the page when it finishes.
  var box = document.getElementById("running");
  if (box) {
    var id = box.dataset.run;
    setInterval(function () {
      fetch("/api/run/" + id).then(function (r) { return r.json(); }).then(function (d) {
        if (d.status && d.status !== "running") { window.location.reload(); }
      });
    }, 1500);
  }
  // Auto-refresh the pipeline page while a GitHub run is in progress.
  var auto = document.getElementById("autorefresh");
  if (auto) { setTimeout(function () { window.location.reload(); }, (+auto.dataset.seconds || 10) * 1000); }
  // Select-all checkbox in the test case table.
  var all = document.getElementById("check-all");
  if (all) {
    all.addEventListener("change", function () {
      document.querySelectorAll('input[name="selected"]').forEach(function (c) { c.checked = all.checked; });
    });
  }
  // Example chips fill the requirement box.
  document.querySelectorAll(".chip-btn").forEach(function (b) {
    b.addEventListener("click", function () { document.getElementById("story").value = b.dataset.story; });
  });
})();
