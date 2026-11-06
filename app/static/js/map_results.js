// Part 3 layers on the shared risk map: UPZ risk fill, report heat map, period, search and zone detail.
(function () {
  const css = name => getComputedStyle(document.documentElement).getPropertyValue('--' + name).trim();
  const fold = text => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  const LEVEL_LABEL = {low: 'Low', medium: 'Medium', high: 'High'};
  const PERIOD_LABEL = {1: 'last month', 3: '3 months', 12: '12 months'};
  const TYPE_LABEL = {
    household: 'Household',
    construction_debris: 'Debris',
    bulky: 'Bulky',
    organic: 'Organic',
    mixed: 'Mixed'
  };
  const HEAT_GRADIENT = {
    0.2: '#cfe5d6',
    0.5: '#f1c98f',
    0.75: '#e98f86',
    1: '#d9706a'
  };

  function getJson(url) {
    return fetch(url).then(r => {
      if (!r.ok) throw new Error(url + ' returned ' + r.status);
      return r.json();
    });
  }

  function initMapResults(risk, urls) {
    const {map} = risk;
    const state = {months: 3, locality: '', zones: {}, showRisk: true, selected: null};
    const heat = L.heatLayer([], {
      radius: 18,
      blur: 22,
      maxZoom: 15,
      minOpacity: .25,
      gradient: HEAT_GRADIENT
    }).addTo(map);

    const $ = id => document.getElementById(id);

    function riskStyle(feature) {
      const zone = state.zones[feature.properties.code];
      const base = {color: css('map-line'), weight: .6, opacity: .45};

      if (!state.showRisk || !zone || !zone.level) {
        return {...base, fillColor: css('brand'), fillOpacity: .06};
      }

      return {...base, fillColor: css(zone.level), fillOpacity: .32};
    }

    function tooltip(code, name) {
      const zone = state.zones[code];
      if (!zone) return name;

      const level = zone.level
        ? `${LEVEL_LABEL[zone.level]} risk`
        : 'No prediction yet';

      return `${name}<br><small>${level} · ${zone.reports} reports</small>`;
    }

    function restyle() {
      if (!risk.layers.upz) return;

      // Keep resetStyle in map.js synchronized with the risk colors.
      risk.layers.upz.options.style = riskStyle;
      risk.layers.upz.setStyle(riskStyle);

      risk.layers.upz.eachLayer(layer => {
        const p = layer.feature.properties;
        layer.setTooltipContent(tooltip(p.code, p.name));
      });
    }

    function fillDetail(code) {
      state.selected = code;
      const zone = state.zones[code];
      if (!zone) return;

      $('detailRisk').innerHTML = zone.level
        ? `<span class="pill ${zone.level}"><span class="dot"></span>${LEVEL_LABEL[zone.level]} risk · ${Math.round(zone.probability * 100)}%</span>`
        : '<span class="pill none">No prediction yet</span>';

      $('detailReportsLabel').textContent = `Reports · ${PERIOD_LABEL[state.months]}`;
      $('detailReports').textContent = zone.reports;
      $('detailOpen').textContent = zone.open;
      $('detailType').textContent = zone.top_type ? TYPE_LABEL[zone.top_type] : '–';
      $('detailVectors').textContent = zone.reports
        ? Math.round(zone.vectors_share * 100) + '%'
        : '–';
    }

    function loadRisk() {
      return getJson(`${urls.riskUrl}?months=${state.months}`).then(data => {
        state.zones = Object.fromEntries(data.zones.map(z => [z.code, z]));

        $('statReports').textContent = data.totals.reports.toLocaleString('en');
        $('statHigh').textContent = data.period ? data.totals.high : '–';
        $('reportsLabel').textContent = `Reports · ${PERIOD_LABEL[state.months]}`;

        if (data.period) {
          const month = new Date(data.period + 'T12:00:00')
            .toLocaleDateString('en', {month: 'long', year: 'numeric'});

          $('riskPeriod').textContent = `Risk predicted for ${month}`;
        }

        restyle();

        if (state.selected) fillDetail(state.selected);
      });
    }

    function loadHeat() {
      const params = new URLSearchParams({months: state.months});
      if (state.locality) params.set('locality', state.locality);

      return getJson(`${urls.heatmapUrl}?${params}`)
        .then(data => heat.setLatLngs(data.points));
    }

    // Period chips
    $('period').addEventListener('click', e => {
      const button = e.target.closest('button[data-months]');
      if (!button) return;

      state.months = Number(button.dataset.months);

      $('period').querySelectorAll('button').forEach(b => {
        b.classList.toggle('on', b === button);
      });

      loadRisk();
      loadHeat();
    });

    // Layer switches
    document.querySelectorAll('.layers .switch').forEach(input => {
      input.addEventListener('change', () => {
        const on = input.checked;

        if (input.dataset.layer === 'heat') {
          on ? heat.addTo(map) : map.removeLayer(heat);
        }

        if (input.dataset.layer === 'risk') {
          state.showRisk = on;
          restyle();
        }

        if (input.dataset.layer === 'labels' && risk.layers.labels) {
          on ? risk.layers.labels.addTo(map) : map.removeLayer(risk.layers.labels);
        }
      });
    });

    $('locSelect').addEventListener('change', e => {
      state.locality = e.target.value;
      loadHeat();
    });

    document.addEventListener('themechange', restyle);

    // Search: UPZ names from loaded zones, neighborhoods from the API.
    const input = $('zoneSearch');
    const list = $('searchResults');

    let shapes = null;
    let highlight = null;
    let timer = null;

    function closeList() {
      list.hidden = true;
      list.innerHTML = '';
    }

    function upzLayer(code) {
      let found = null;

      risk.layers.upz.eachLayer(layer => {
        if (layer.feature.properties.code === code) found = layer;
      });

      return found;
    }

    function showUpz(code) {
      const layer = upzLayer(code);
      if (!layer) return;

      map.fitBounds(layer.getBounds(), {
        maxZoom: 15,
        padding: [40, 40]
      });

      layer.fire('click', {
        latlng: layer.getBounds().getCenter()
      });
    }

    function showNeighborhood(item) {
      const loaded = shapes || getJson(urls.neighborhoodShapesUrl)
        .then(data => (shapes = data));

      Promise.resolve(loaded).then(data => {
        const point = L.latLng(item.lat, item.lon);

        const feature = data.features.find(f =>
          f.properties.name === item.name &&
          L.geoJSON(f).getBounds().contains(point)
        );

        if (highlight) map.removeLayer(highlight);
        highlight = null;

        // No shape for this name around the point: just center the map on it.
        if (!feature) {
          map.setView(point, 16);
          return;
        }

        highlight = L.geoJSON(feature, {
          interactive: false,
          style: {
            color: css('brand'),
            weight: 2.5,
            dashArray: '6 4',
            fillOpacity: .08,
            fillColor: css('brand')
          }
        }).addTo(map);

        map.fitBounds(highlight.getBounds(), {
          maxZoom: 16,
          padding: [60, 60]
        });
      });
    }

    function render(items) {
      list.innerHTML = '';

      items.forEach(item => {
        const li = document.createElement('li');
        const button = document.createElement('button');

        button.type = 'button';
        button.innerHTML = `<i class="bi bi-${item.kind === 'upz' ? 'bounding-box' : 'house'}"></i><span></span><small></small>`;

        button.querySelector('span').textContent = item.name;

        button.querySelector('small').textContent =
          item.kind === 'upz'
            ? 'UPZ · ' + item.locality
            : 'Neighborhood';

        button.addEventListener('click', () => {
          input.value = item.name;
          closeList();

          item.kind === 'upz'
            ? showUpz(item.code)
            : showNeighborhood(item);
        });

        li.appendChild(button);
        list.appendChild(li);
      });

      list.hidden = items.length === 0;
    }

    input.addEventListener('input', () => {
      clearTimeout(timer);

      const q = input.value.trim();

      if (q.length < 2) {
        closeList();
        return;
      }

      timer = setTimeout(() => {
        const upz = Object.values(state.zones)
          .filter(z => fold(z.name).includes(fold(q)))
          .slice(0, 4)
          .map(z => ({
            kind: 'upz',
            code: z.code,
            name: z.name,
            locality: z.locality
          }));

        getJson(`${urls.neighborhoodsUrl}?q=${encodeURIComponent(q)}`)
          .then(hoods => render(
            upz.concat(hoods.slice(0, 6).map(h => ({
              kind: 'hood',
              ...h
            })))
          ))
          .catch(() => render(upz));
      }, 200);
    });

    input.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeList();

      if (e.key === 'Enter') {
        const first = list.querySelector('button');
        if (first) first.click();
      }
    });

    document.addEventListener('click', e => {
      if (!e.target.closest('.search')) closeList();
    });

    risk.ready.then(() => {
      risk.layers.upz.on('click', e => {
        fillDetail(e.layer.feature.properties.code);
      });

      // "See on the map" from My reports opens the map on that point.
      const params = new URLSearchParams(location.search);
      const lat = parseFloat(params.get('lat'));
      const lon = parseFloat(params.get('lon'));

      if (Number.isFinite(lat) && Number.isFinite(lon)) {
        L.circleMarker([lat, lon], {
          radius: 9,
          color: css('brand'),
          weight: 3,
          fillOpacity: .25
        }).addTo(map);

        map.setView([lat, lon], 16);
      }

      return Promise.all([loadRisk(), loadHeat()]);
    }).catch(() => {});
  }

  window.initMapResults = initMapResults;
})();