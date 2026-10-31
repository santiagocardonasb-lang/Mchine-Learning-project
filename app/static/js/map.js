// Shared Leaflet setup: themed Esri tiles and the Bogotá UPZ / locality boundaries.
(function () {
  const BOGOTA = [4.63, -74.11];
  const css = name => getComputedStyle(document.documentElement).getPropertyValue('--' + name).trim();
  const tileUrl = () => document.documentElement.classList.contains('dark')
    ? 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}'
    : 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}';
  const upzStyle = () => ({color: css('map-line'), weight: .6, opacity: .45, fillColor: css('brand'), fillOpacity: .06});
  const localityStyle = () => ({color: css('map-line'), weight: 1.2, opacity: .7, fill: false});

  function getJson(url) {
    return fetch(url).then(r => {
      if (!r.ok) throw new Error(url + ' returned ' + r.status);
      return r.json();
    });
  }

  // A map with the theme-aware base tiles only (the report page uses it for the pin).
  function initBaseMap(el, leafletOptions) {
    const map = L.map(el, Object.assign({zoomControl: false, attributionControl: false}, leafletOptions));
    L.control.attribution({position: 'bottomleft', prefix: false}).addAttribution('Tiles &copy; Esri').addTo(map);
    // Esri's canvas tiles stop at 16; past that Leaflet scales them so a pin can be placed precisely.
    const tiles = L.tileLayer(tileUrl(), {maxNativeZoom: 16, maxZoom: 18}).addTo(map);
    document.addEventListener('themechange', () => tiles.setUrl(tileUrl()));
    return map;
  }

  // options: upzUrl, localitiesUrl, interactive (default true), fitOptions (Leaflet fitBounds
  // options for the city view), onUpzClick(feature, latlng).
  // Returns {map, layers, ready}: layers gets upz, localities and labels once ready resolves.
  function initRiskMap(el, options) {
    const o = Object.assign({interactive: true, fitOptions: {padding: [20, 20]}}, options);
    const frozen = {dragging: false, scrollWheelZoom: false, doubleClickZoom: false,
                    touchZoom: false, boxZoom: false, keyboard: false};
    // Quarter-step zoom lets fitBounds fill the view; whole steps leave the tall city small.
    const map = initBaseMap(el, Object.assign({zoomSnap: .25}, o.interactive ? {} : frozen)).setView(BOGOTA, 11);
    if (o.interactive) L.control.zoom({position: 'bottomleft'}).addTo(map);
    const layers = {};

    function bindUpz(feature, layer) {
      layer.bindTooltip(feature.properties.name, {sticky: true, className: 'zone-tip'});
      layer.on('mouseover', () => layer.setStyle({weight: 2, opacity: .8, fillOpacity: .16}));
      layer.on('mouseout', () => layers.upz.resetStyle(layer));
      if (o.onUpzClick) layer.on('click', e => o.onUpzClick(feature, e.latlng));
    }

    function label(feature) {
      return L.marker(L.geoJSON(feature).getBounds().getCenter(), {
        interactive: false,
        icon: L.divIcon({className: 'loc-label', html: feature.properties.name, iconSize: null}),
      });
    }

    function fitCity() {
      if (layers.upz) map.fitBounds(layers.upz.getBounds(), o.fitOptions);
    }

    const ready = Promise.all([getJson(o.upzUrl), getJson(o.localitiesUrl)]).then(([upz, localities]) => {
      layers.upz = L.geoJSON(upz, {
        style: upzStyle, interactive: o.interactive, onEachFeature: o.interactive ? bindUpz : null,
      }).addTo(map);
      layers.localities = L.geoJSON(localities, {style: localityStyle, interactive: false}).addTo(map);
      // Names would clutter the small home preview, so only the full map shows them.
      if (o.interactive) layers.labels = L.layerGroup(localities.features.map(label)).addTo(map);
      fitCity();
      return {upz, localities};
    });
    ready.catch(() => {
      const message = document.createElement('div');
      message.className = 'map-error';
      message.textContent = "Couldn't load the zone boundaries. Try reloading the page.";
      el.appendChild(message);
    });

    new ResizeObserver(() => {
      map.invalidateSize();
      // A frozen map can't be panned, so keep the whole city in view at every size.
      if (!o.interactive) fitCity();
    }).observe(el);

    document.addEventListener('themechange', () => {
      if (layers.upz) layers.upz.setStyle(upzStyle());
      if (layers.localities) layers.localities.setStyle(localityStyle());
    });

    return {map, layers, ready};
  }

  window.initBaseMap = initBaseMap;
  window.initRiskMap = initRiskMap;
})();
