/**
* Template Name: Selecao
* Template URL: https://bootstrapmade.com/selecao-bootstrap-template/
* Updated: Aug 07 2024 with Bootstrap v5.3.3
* Author: BootstrapMade.com
* License: https://bootstrapmade.com/license/
*/

(function () {
  "use strict";

  /**
   * Apply .scrolled class to the body as the page is scrolled down
   */
  function toggleScrolled() {
    const selectBody = document.querySelector('body');
    const selectHeader = document.querySelector('#header');
    if (!selectHeader.classList.contains('scroll-up-sticky') && !selectHeader.classList.contains('sticky-top') && !selectHeader.classList.contains('fixed-top')) return;
    window.scrollY > 100 ? selectBody.classList.add('scrolled') : selectBody.classList.remove('scrolled');
  }

  document.addEventListener('scroll', toggleScrolled);
  window.addEventListener('load', toggleScrolled);

  /**
   * Mobile nav toggle
   */
  const mobileNavToggleBtn = document.querySelector('.mobile-nav-toggle');

  function mobileNavToogle() {
    document.querySelector('body').classList.toggle('mobile-nav-active');
    mobileNavToggleBtn.classList.toggle('bi-list');
    mobileNavToggleBtn.classList.toggle('bi-x');
  }
  mobileNavToggleBtn.addEventListener('click', mobileNavToogle);

  /**
   * Hide mobile nav on same-page/hash links
   */
  document.querySelectorAll('#navmenu a').forEach(navmenu => {
    navmenu.addEventListener('click', () => {
      if (document.querySelector('.mobile-nav-active')) {
        mobileNavToogle();
      }
    });

  });

  /**
   * Toggle mobile nav dropdowns
   */
  document.querySelectorAll('.navmenu .toggle-dropdown').forEach(navmenu => {
    navmenu.addEventListener('click', function (e) {
      e.preventDefault();
      this.parentNode.classList.toggle('active');
      this.parentNode.nextElementSibling.classList.toggle('dropdown-active');
      e.stopImmediatePropagation();
    });
  });

  /**
   * Preloader
   */
  const preloader = document.querySelector('#preloader');
  if (preloader) {
    window.addEventListener('load', () => {
      preloader.remove();
    });
  }

  /**
   * Scroll top button
   */
  let scrollTop = document.querySelector('.scroll-top');

  function toggleScrollTop() {
    if (scrollTop) {
      window.scrollY > 100 ? scrollTop.classList.add('active') : scrollTop.classList.remove('active');
    }
  }
  scrollTop.addEventListener('click', (e) => {
    e.preventDefault();
    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  });

  window.addEventListener('load', toggleScrollTop);
  document.addEventListener('scroll', toggleScrollTop);

  /**
   * Animation on scroll function and init
   */
  function aosInit() {
    AOS.init({
      duration: 600,
      easing: 'ease-in-out',
      once: true,
      mirror: false
    });
  }
  window.addEventListener('load', aosInit);

  /**
   * Initiate glightbox
   */
  const glightbox = GLightbox({
    selector: '.glightbox'
  });

  /**
   * Init isotope layout and filters
   */
  document.querySelectorAll('.isotope-layout').forEach(function (isotopeItem) {
    let layout = isotopeItem.getAttribute('data-layout') ?? 'masonry';
    let filter = isotopeItem.getAttribute('data-default-filter') ?? '*';
    let sort = isotopeItem.getAttribute('data-sort') ?? 'original-order';

    let initIsotope;
    imagesLoaded(isotopeItem.querySelector('.isotope-container'), function () {
      initIsotope = new Isotope(isotopeItem.querySelector('.isotope-container'), {
        itemSelector: '.isotope-item',
        layoutMode: layout,
        filter: filter,
        sortBy: sort
      });
    });

    isotopeItem.querySelectorAll('.isotope-filters li').forEach(function (filters) {
      filters.addEventListener('click', function () {
        isotopeItem.querySelector('.isotope-filters .filter-active').classList.remove('filter-active');
        this.classList.add('filter-active');
        initIsotope.arrange({
          filter: this.getAttribute('data-filter')
        });
        if (typeof aosInit === 'function') {
          aosInit();
        }
      }, false);
    });

  });

  /**
   * Init swiper sliders
   */
  function initSwiper() {
    document.querySelectorAll(".init-swiper").forEach(function (swiperElement) {
      let config = JSON.parse(
        swiperElement.querySelector(".swiper-config").innerHTML.trim()
      );

      if (swiperElement.classList.contains("swiper-tab")) {
        initSwiperWithCustomPagination(swiperElement, config);
      } else {
        new Swiper(swiperElement, config);
      }
    });
  }

  window.addEventListener("load", initSwiper);

  /**
   * Correct scrolling position upon page load for URLs containing hash links.
   */
  window.addEventListener('load', function (e) {
    if (window.location.hash) {
      if (document.querySelector(window.location.hash)) {
        setTimeout(() => {
          let section = document.querySelector(window.location.hash);
          let scrollMarginTop = getComputedStyle(section).scrollMarginTop;
          window.scrollTo({
            top: section.offsetTop - parseInt(scrollMarginTop),
            behavior: 'smooth'
          });
        }, 100);
      }
    }
  });

  /**
   * Navmenu Scrollspy
   */
  let navmenulinks = document.querySelectorAll('.navmenu a');

  function navmenuScrollspy() {
    navmenulinks.forEach(navmenulink => {
      if (!navmenulink.hash) return;
      let section = document.querySelector(navmenulink.hash);
      if (!section) return;
      let position = window.scrollY + 200;
      if (position >= section.offsetTop && position <= (section.offsetTop + section.offsetHeight)) {
        document.querySelectorAll('.navmenu a.active').forEach(link => link.classList.remove('active'));
        navmenulink.classList.add('active');
      } else {
        navmenulink.classList.remove('active');
      }
    })
  }
  window.addEventListener('load', navmenuScrollspy);
  document.addEventListener('scroll', navmenuScrollspy);

})();















// JS FOR MODALS



// Listen for clicks on the service wrappers
document.querySelectorAll('.service-wrapper').forEach(item => {
  item.addEventListener('click', function () {
    // Get the data associated with the clicked service wrapper
    const serviceData = item.getAttribute('data-service');

    // Update the modal content based on the clicked service item
    let modalContent = '';


    // For 1st services
    if (serviceData === 'service1') {
      modalContent = `
<div class="custom-link-box">
  <a href="/Patentability-Search" class="custom-link">Patentabilty/Novelty Search</a>
</div>

<div class="custom-link-box">
  <a href="/FTO-Freedom-To-Operate" class="custom-link">FTO (Freedom To Operate)</a>
</div>

<div class="custom-link-box">
  <a href="/Infringement-Search" class="custom-link">Infringement Search</a>
</div>

<div class="custom-link-box">
  <a href="/Non-Patent-Literature-NPL-Search" class="custom-link">Non- Patent Literature (NPL) Search</a>
</div>

<div class="custom-link-box">
  <a href="/Design-Patent-Search" class="custom-link">Design Patent Search</a>
</div>

<div class="custom-link-box">
  <a href="/Knock-Out-Search" class="custom-link">Knock Out Search</a>
</div>

<div class="custom-link-box">
  <a href="/State-Of-Art-Search" class="custom-link">State Of Art Search</a>
</div>

<div class="custom-link-box">
  <a href="/Chemical-Structure-Searches" class="custom-link">Chemical Structure Searches</a>
</div>



      `;
    }



    // For 2st services

    if (serviceData === 'service2') {
      modalContent = `
<div class="custom-link-box">
  <a href="Invalidation-Validation-Search" class="custom-link">Invalidation/Validation Search</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Infringement-Non-Infringement-Analysis" class="custom-link">Infringement/Non-Infringement Analysis</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Evidence-Of-Use-Claim-Charts" class="custom-link">Evidence Of Use / Claim Charts</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Pre-Grant-And-Post-Grant-Opposition" class="custom-link">Pre Grant And Post Grant Opposition</a>
</div>

      `;
    }




    // For 3st services
    if (serviceData === 'service3') {
      modalContent = `
<div class="custom-link-box">
  <a href="Office-Action-Response-Drafting" class="custom-link">Office Action Response Drafting</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Patent-Drawings" class="custom-link">Patent Drawings & Illustrations</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Patent-Drafting" class="custom-link">Patent Drafting (Provisional & Non-Provisional)</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Patent-Filing" class="custom-link">Patent Filing</a>
</div>
      `;
    }



    // For 4st services
    if (serviceData === 'service4') {
      modalContent = `
<div class="custom-link-box">
  <a href="Landscape-Analysis" class="custom-link">Landscape Analysis</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Patent-Portfolio-Analysis" class="custom-link">Patent Portfolio Analysis</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Patent-Valuation" class="custom-link">Patent Valuation</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="White-space-Analysis" class="custom-link">White-space Analysis</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Technology-Scouting" class="custom-link">Technology Scouting</a>
</div>

      `;
    }




    // For 5st services
    if (serviceData === 'service5') {
      modalContent = `
<div class="custom-link-box">
  <a href="Patent-Licensing" class="custom-link">Patent Licensing</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Detailed-Claim-Charts" class="custom-link">Detailed Claim Charts</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Due-Diligence" class="custom-link">Due Diligence</a>
</div>

      `;
    }







    // For 6st services

    else if (serviceData === 'service6') {
      modalContent = `
<div class="custom-link-box">
  <a href="Docketing-Support" class="custom-link">Docketing Support Services</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="IDS-Preparation" class="custom-link">IDS Preparation</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="PCT-Filing" class="custom-link">PCT Filing</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Patent-Proof-Reading" class="custom-link">Patent Proof Reading</a>
</div>
<hr>
<div class="custom-link-box">
  <a href="Patent-Application-Preparation" class="custom-link">Patent Application Form Preparation</a>
</div>

      `;
    }

    // Inject the dynamic content into the modal body
    document.getElementById('modalContent').innerHTML = modalContent;
  });
});






