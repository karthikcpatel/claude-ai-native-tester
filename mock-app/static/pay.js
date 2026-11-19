(function () {
  var form = document.getElementById("pay-form");
  var button = document.getElementById("pay-button");
  var result = document.getElementById("result");
  var fields = ["cardholder", "card", "expiry", "cvc", "amount"];

  function clearErrors() {
    fields.forEach(function (name) {
      var error = document.getElementById(name + "-error");
      var input = document.getElementById(name);
      error.hidden = true; error.textContent = "";
      input.removeAttribute("aria-invalid"); input.removeAttribute("aria-describedby");
    });
    result.textContent = "";
  }

  function showResult(kind, text) {
    var p = document.createElement("p");
    p.className = kind; p.textContent = text;
    result.textContent = ""; result.appendChild(p);
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (button.disabled) { return; }
    clearErrors();
    button.disabled = true;
    var payload = { idempotency_key: document.getElementById("idempotency-key").value };
    fields.forEach(function (name) { payload[name] = document.getElementById(name).value; });
    fetch("/api/payments", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": payload.idempotency_key },
      body: JSON.stringify(payload)
    }).then(function (response) {
      return response.json().then(function (data) { return { status: response.status, data: data }; });
    }).then(function (r) {
      if (r.status === 422) {
        var first = null;
        Object.keys(r.data.errors).forEach(function (name) {
          var error = document.getElementById(name + "-error");
          var input = document.getElementById(name);
          error.textContent = r.data.errors[name]; error.hidden = false;
          input.setAttribute("aria-invalid", "true"); input.setAttribute("aria-describedby", name + "-error");
          if (!first) { first = input; }
        });
        showResult("fail", "Check the highlighted fields. No payment was made.");
        if (first) { first.focus(); }
      } else if (r.status === 200 && r.data.status === "approved") {
        showResult("ok", "Payment approved. Reference " + r.data.payment_id + ".");
      } else {
        showResult("fail", r.data.message || "The payment could not be completed.");
      }
    }).catch(function () {
      showResult("fail", "The payment could not be completed. You have not been charged.");
    }).then(function () { button.disabled = false; });
  });
})();
