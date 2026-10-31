// Report page: movable pin, zone lookup and stepper. The server re-checks everything on submit.
(function () {
  const form = document.getElementById('reportForm');
  const latInput = form.elements.latitude;
  const lonInput = form.elements.longitude;
  const chips = document.getElementById('zoneChips');
  const submit = document.getElementById('sendReport');
  const steps = document.getElementById('stepper').children;
  const brand = () => getComputedStyle(document.documentElement).getPropertyValue('--brand').trim();

  let start = [parseFloat(latInput.value), parseFloat(lonInput.value)];
  if (start.some(Number.isNaN)) start = [4.63, -74.11];

  const map = initBaseMap(document.getElementById('reportMap')).setView(start, 15);
  L.control.zoom({position: 'bottomright'}).addTo(map);
  const pin = L.circleMarker(start, {radius: 10, color: '#fff', weight: 3, fillColor: brand(), fillOpacity: 1}).addTo(map);
  new ResizeObserver(() => map.invalidateSize()).observe(map.getContainer());
  document.addEventListener('themechange', () => pin.setStyle({fillColor: brand()}));

  let located = false;
  let lookup = 0;

  function chip(label, value, error) {
    const el = document.createElement('div');
    el.className = error ? 'chip error' : 'chip';
    if (label) {
      const span = document.createElement('span');
      span.textContent = label;
      el.append(span);
    }
    el.append(value);
    return el;
  }

  function updateStepper() {
    const described = form.querySelector('[name=waste_type]:checked') && form.querySelector('[name=size]:checked');
    steps[0].className = located ? 'done' : 'on';
    steps[1].className = !located ? '' : described ? 'done' : 'on';
    steps[2].className = located && described ? 'on' : '';
  }

  function locate(latlng) {
    latInput.value = latlng.lat.toFixed(6);
    lonInput.value = latlng.lng.toFixed(6);
    const id = ++lookup;
    located = false;
    submit.disabled = true;
    chips.replaceChildren(chip('', 'Finding the zone…'));
    updateStepper();
    const query = new URLSearchParams({lat: latInput.value, lon: lonInput.value});
    fetch(form.dataset.locateUrl + '?' + query)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(zone => {
        if (id !== lookup) return;  // the pin moved again while this request was in flight
        const items = [chip('Locality', zone.locality_name), chip('UPZ', zone.upz_name)];
        if (zone.neighborhood) items.push(chip('Neighborhood', zone.neighborhood));
        chips.replaceChildren(...items);
        located = true;
        submit.disabled = false;
        updateStepper();
      })
      .catch(status => {
        if (id !== lookup) return;
        if (status === 404) {
          chips.replaceChildren(chip('', 'Outside the covered area', true));
        } else {
          // Lookup failed for another reason; let the server decide on submit.
          chips.replaceChildren(chip('', "Couldn't detect the zone", true));
          submit.disabled = false;
        }
      });
  }

  map.on('click', e => {
    pin.setLatLng(e.latlng);
    locate(e.latlng);
  });
  form.addEventListener('change', updateStepper);
  locate(L.latLng(start));
})();
