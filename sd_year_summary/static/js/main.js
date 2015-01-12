$(document).ready(function() {
    $('.bin').imagesLoaded(function(){
        $('.bin').packery({
            itemSelector: '.game',
            gutter: 4,
        });
    });

    $('.game').hover(function() {
        $('.game__tooltip', this).fadeIn();
    }, function() {
        $('.game__tooltip', this).fadeOut();
    });
});
