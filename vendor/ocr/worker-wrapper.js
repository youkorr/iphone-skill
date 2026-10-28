// Point d'entrée du worker de lecture. Les données de langue sont servies depuis fra-traineddata.js
// (base64), car certains hébergeurs refusent les fichiers .gz : on répond nous-mêmes à leur requête.
importScripts("fra-traineddata.js");

var realFetch = self.fetch.bind(self);
self.fetch = function (url, opts) {
  if (String(url).indexOf("fra.traineddata") !== -1) {
    var bin = atob(self.PLACE_NETTE_FRA);
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return Promise.resolve(new Response(bytes));
  }
  return realFetch(url, opts);
};

importScripts("worker.min.js");
