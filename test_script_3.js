
    
    
            var map_c346b429699ec990174b11dec116f430 = L.map(
                "map_c346b429699ec990174b11dec116f430",
                {
                    center: [40.963087, 69.951901],
                    
                    ...{
  "zoom": 1,
  "zoomControl": true,
  "preferCanvas": false,
}

                }
            );

            

        
    
            var image_overlay_f279d8cb087e2dc1f61f22a54e45a29f = L.imageOverlay("file:///C:/IRLAND/Road_Safety_Audit/ndvi_overlay.png",
                [[40.963087, 69.951901], [41.007913, 70.091050]],
                {
}
            );
        
    
            image_overlay_f279d8cb087e2dc1f61f22a54e45a29f.addTo(map_c346b429699ec990174b11dec116f430);
        
    
            var marker_ff2a87151a3c561946615c3d9be2c828 = L.marker(
                [40.963087, 69.951901],
                {
}
            ).addTo(map_c346b429699ec990174b11dec116f430);
        
    
            var div_icon_5aca1fc6bb08dd85a00901e0fea3e1d0 = L.divIcon({
  "html": "\u003cdiv id=\"map-direction-arrow\" class=\"custom-arrow\" style=\"font-size: 24px; color: gray; text-shadow: 1px 1px 2px white; line-height: 24px; text-align: center; transform-origin: 50% 100%; transition: transform 0.3s ease;\"\u003e\u25b2\u003c/div\u003e",
  "iconSize": [24, 24],
  "iconAnchor": [12, 24],
  "className": "empty",
});
        
    
                marker_ff2a87151a3c561946615c3d9be2c828.setIcon(div_icon_5aca1fc6bb08dd85a00901e0fea3e1d0);

    
              var circle_ndvi = L.circle(
                  [41.006024, 70.088589],
                  {"bubblingMouseEvents": true, "color": "blue", "dashArray": null, "dashOffset": null, "fill": false, "fillColor": "blue", "fillOpacity": 0.2, "fillRule": "evenodd", "lineCap": "round", "lineJoin": "round", "opacity": 1.0, "radius": 50, "stroke": true, "weight": 3}
              ).addTo(map_c346b429699ec990174b11dec116f430);


    map_c346b429699ec990174b11dec116f430.on("click", function(e) {
        window.parent.postMessage({ type: "mapClick", lat: e.latlng.lat, lon: e.latlng.lng }, "*");
    });
      window.addEventListener("message", function(e) {

        if(e.data.lat && e.data.lon) {
            map_c346b429699ec990174b11dec116f430.setView([e.data.lat, e.data.lon], 18);
            marker_ff2a87151a3c561946615c3d9be2c828.setLatLng([e.data.lat, e.data.lon]);
            if(typeof circle_ndvi !== "undefined") circle_ndvi.setLatLng([e.data.lat, e.data.lon]);
            if(e.data.heading !== undefined) {
                var arrow = document.getElementById("map-direction-arrow");
                if(arrow) arrow.style.transform = "rotate(" + e.data.heading + "deg)";
            }
            if(e.data.popupText) {
                var popup = marker_ff2a87151a3c561946615c3d9be2c828.getPopup();
                if(popup) {
                    popup.setContent("<div style=\"width: 100.0%; height: 100.0%;\">" + e.data.popupText + "</div>");
                }
            }
        }
    });

