/* The one behaviour the board has: a filter over the cards.

   Written to work with the script at the end of the body and no listener on
   load, so the page is usable the moment it paints. */
(function () {
  var box = document.createElement('input');
  box.type = 'search';
  box.placeholder = 'filter cards';
  box.className = 'filter';
  document.querySelector('header .sub').insertAdjacentElement('afterend', box);

  var cards = [].slice.call(document.querySelectorAll('.card'));
  cards.forEach(function (card) {
    card.dataset.hay = card.textContent.toLowerCase();
  });

  box.addEventListener('input', function () {
    var needle = box.value.trim().toLowerCase();
    cards.forEach(function (card) {
      card.hidden = !!needle && card.dataset.hay.indexOf(needle) === -1;
    });
    /* A column whose cards are all filtered out says so, rather than sitting
       there looking like a column that is genuinely empty. */
    document.querySelectorAll('.col').forEach(function (col) {
      var live = col.querySelectorAll('.card:not([hidden])').length;
      var empty = col.querySelector('.empty');
      if (empty) { empty.hidden = !!needle && live > 0; }
      col.classList.toggle('filtered', !!needle && live === 0);
    });
  });
})();
