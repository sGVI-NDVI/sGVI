
    
    
            var map_466ee76075e490bb08a99061ec17fbaa = L.map(
                "map_466ee76075e490bb08a99061ec17fbaa",
                {
                    center: [41.006024, 70.088589],
                    crs: L.CRS.EPSG3857,
                    ...{
  "zoom": 14,
  "zoomControl": true,
  "preferCanvas": false,
}

                }
            );

            

        
    
            var tile_layer_a2e124e13fe52dce79f8dbcc97f75d71 = L.tileLayer(
                "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                {
  "minZoom": 0,
  "maxZoom": 19,
  "maxNativeZoom": 19,
  "noWrap": false,
  "attribution": "\u0026copy; \u003ca href=\"https://www.openstreetmap.org/copyright\"\u003eOpenStreetMap\u003c/a\u003e contributors",
  "subdomains": "abc",
  "detectRetina": false,
  "tms": false,
  "opacity": 1,
}

            );
        
    
            tile_layer_a2e124e13fe52dce79f8dbcc97f75d71.addTo(map_466ee76075e490bb08a99061ec17fbaa);
        
    
            var image_overlay_6da6a2f2e0273f4a57182127cb66fbe7 = L.imageOverlay("file:///C:/IRLAND/Road_Safety_Audit/ndvi_overlay.png",
                [[40.963087124321774, 69.95190100591554], [41.007913056999335, 70.09105004342565]],
                {
  "opacity": 0.7,
  "interactive": true,
}
            );
        
    
            image_overlay_6da6a2f2e0273f4a57182127cb66fbe7.addTo(map_466ee76075e490bb08a99061ec17fbaa);
        
    
            var marker_71b8ad8301d20b218ac900ae41d296bb = L.marker(
                [41.006024, 70.088589],
                {
}
            ).addTo(map_466ee76075e490bb08a99061ec17fbaa);
        
    
        var popup_2e98bd2e1dd9cd68f14582d0e1b65628 = L.popup({
  "maxWidth": "100%",
});

        
            
                var html_99d2a4ca9979c454f3f8b85670cf1085 = $(`<div id="html_99d2a4ca9979c454f3f8b85670cf1085" style="width: 100.0%; height: 100.0%;">pt00000</div>`)[0];
                popup_2e98bd2e1dd9cd68f14582d0e1b65628.setContent(html_99d2a4ca9979c454f3f8b85670cf1085);
            
        

        marker_71b8ad8301d20b218ac900ae41d296bb.bindPopup(popup_2e98bd2e1dd9cd68f14582d0e1b65628)
        ;

        
    
    
            var circle_52cade36b1af4388ffd375563895fba3 = L.circle(
                [41.006024, 70.088589],
                {"bubblingMouseEvents": true, "color": "blue", "dashArray": null, "dashOffset": null, "fill": false, "fillColor": "blue", "fillOpacity": 0.2, "fillRule": "evenodd", "lineCap": "round", "lineJoin": "round", "opacity": 1.0, "radius": 50, "stroke": true, "weight": 3}
            ).addTo(map_466ee76075e490bb08a99061ec17fbaa);
        
    
            var layer_control_81d5eba67a2392e42186f86a8c3495ad_layers = {
                base_layers : {
                    "openstreetmap" : tile_layer_a2e124e13fe52dce79f8dbcc97f75d71,
                },
                overlays :  {
                    "Full Route NDVI (Sentinel-2)" : image_overlay_6da6a2f2e0273f4a57182127cb66fbe7,
                },
            };
            let layer_control_81d5eba67a2392e42186f86a8c3495ad = L.control.layers(
                layer_control_81d5eba67a2392e42186f86a8c3495ad_layers.base_layers,
                layer_control_81d5eba67a2392e42186f86a8c3495ad_layers.overlays,
                {
  "position": "topright",
  "collapsed": true,
  "autoZIndex": true,
}
            ).addTo(map_466ee76075e490bb08a99061ec17fbaa);


    map_466ee76075e490bb08a99061ec17fbaa.on("click", function(e) {
        window.parent.postMessage({ type: "mapClick", lat: e.latlng.lat, lon: e.latlng.lng }, "*");
    });
    window.addEventListener("message", function(e) {

          if (e.data.type === "voronoi" && typeof window.voronoiLayer === "undefined") {
              window.voronoiLayer = L.geoJSON(e.data.data, {
                  style: function (feature) {
                      return {color: "#ff7800", weight: 1, fillOpacity: 0.2};
                  }
              }).addTo(map_466ee76075e490bb08a99061ec17fbaa);
          }

        if(e.data.lat && e.data.lon) {
            map_466ee76075e490bb08a99061ec17fbaa.setView([e.data.lat, e.data.lon], 18);
            marker_71b8ad8301d20b218ac900ae41d296bb.setLatLng([e.data.lat, e.data.lon]);
            if(typeof circle_52cade36b1af4388ffd375563895fba3 !== "undefined") circle_52cade36b1af4388ffd375563895fba3.setLatLng([e.data.lat, e.data.lon]);
            if(e.data.heading !== undefined) {
                var arrow = document.getElementById("map-direction-arrow");
                if(arrow) arrow.style.transform = "rotate(" + e.data.heading + "deg)";
            }
            if(e.data.popupText) {
                var popup = marker_71b8ad8301d20b218ac900ae41d296bb.getPopup();
                if(popup) {
                    popup.setContent("<div style=\"width: 100.0%; height: 100.0%;\">" + e.data.popupText + "</div>");
                }
            }
        }
    });
        

    
    