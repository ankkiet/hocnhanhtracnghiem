export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Chuyển tiếp (Reverse Proxy) tất cả API request về backend Koyeb
    if (url.pathname.startsWith('/api/')) {
      const backendUrl = new URL(request.url);
      backendUrl.protocol = 'https:';
      backendUrl.host = 'inland-marylin-hocnhanhtn-c3471a95.koyeb.app';
      backendUrl.port = '';
      return fetch(new Request(backendUrl.toString(), request));
    }

    // Xử lý llms.txt cho AI crawlers & Google PageSpeed Agentic Browsing
    if (url.pathname === '/llms.txt') {
      const assetRes = await env.ASSETS.fetch(request);
      if (assetRes.ok) {
        const headers = new Headers(assetRes.headers);
        headers.set('Content-Type', 'text/plain; charset=utf-8');
        headers.set('Cache-Control', 'public, max-age=86400, stale-while-revalidate=604800');
        return new Response(assetRes.body, { status: 200, headers });
      }
      const llmsContent = `# HocNhanhTN\n\n> Hệ thống học nhanh trắc nghiệm thông minh cho học sinh & giáo viên - Chuẩn GDPT 2018.\n\nHocNhanhTN là nền tảng số hóa đề thi Word (.docx) và PDF thành phòng thi trực tuyến chuẩn Chương trình Giáo dục phổ thông 2018, tự động nhận diện công thức Toán Lý Hóa (LaTeX) và hình ảnh minh họa.\n\n## Tính năng & Liên kết chính\n- [Trang chủ HocNhanhTN](https://hocnhanhtn.online/): Nền tảng số hóa và tổ chức phòng thi trực tuyến.\n- [Kho đề thi](https://hocnhanhtn.online/de-thi): Danh mục đề thi và ôn tập trắc nghiệm.\n- [Quy trình số hóa đề thi](https://hocnhanhtn.online/#quy-trinh): Tự động nhận diện công thức Toán Lý Hóa và hình ảnh minh họa.\n- [Định dạng chuẩn GDPT 2018](https://hocnhanhtn.online/#dang-thuc-gdpt): Trắc nghiệm nhiều lựa chọn, đúng sai, trả lời ngắn.\n- [Studio Biên tập Đề thi](https://hocnhanhtn.online/editor): Giao diện biên soạn và soát lỗi đề thi trực quan.\n- [Giới thiệu về chúng tôi](https://hocnhanhtn.online/about): Sứ mệnh giáo dục, chuyển đổi số và công nghệ AI OCR.\n- [Chính sách bảo mật](https://hocnhanhtn.online/privacy): Cam kết bảo vệ quyền riêng tư người dùng và tuân thủ Google AdSense.\n- [Điều khoản dịch vụ](https://hocnhanhtn.online/terms): Quy định dịch vụ và bản quyền học liệu.\n- [Liên hệ & Hỗ trợ](https://hocnhanhtn.online/contact): Kênh tiếp nhận góp ý và hỗ trợ kỹ thuật 24/7.\n`;
      return new Response(llmsContent, {
        status: 200,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'public, max-age=86400, stale-while-revalidate=604800'
        }
      });
    }

    // Xử lý ai-catalog.json theo chuẩn ARD (Agentic Resource Discovery 1.0)
    if (url.pathname === '/.well-known/ai-catalog.json' || url.pathname === '/ai-catalog.json') {
      const assetRes = await env.ASSETS.fetch(request);
      if (assetRes.ok) {
        const headers = new Headers(assetRes.headers);
        headers.set('Content-Type', 'application/json; charset=utf-8');
        headers.set('Cache-Control', 'public, max-age=86400, stale-while-revalidate=604800');
        return new Response(assetRes.body, { status: 200, headers });
      }
      const catalogData = {
        specVersion: "1.0",
        host: {
          displayName: "HocNhanhTN",
          documentationUrl: "https://hocnhanhtn.online",
          logoUrl: "https://hocnhanhtn.online/unnamed.jpg"
        },
        entries: [
          {
            identifier: "urn:air:hocnhanhtn:quiz:service",
            displayName: "HocNhanhTN Educational Quiz Service",
            type: "application/ai-catalog+json",
            url: "https://hocnhanhtn.online/.well-known/ai-catalog.json",
            description: "Nền tảng số hóa và tổ chức phòng thi trắc nghiệm trực tuyến chuẩn GDPT 2018.",
            tags: ["quiz", "education", "gdpt2018", "vietnam"],
            capabilities: ["DocxQuizParser", "OnlineExamRoom", "MathFormulaOCR"],
            representativeQueries: [
              "tạo đề thi trắc nghiệm online",
              "số hóa đề thi word sang trắc nghiệm",
              "làm bài trắc nghiệm chuẩn gdpt 2018"
            ],
            version: "1.0.0"
          }
        ]
      };
      return new Response(JSON.stringify(catalogData, null, 2), {
        status: 200,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Cache-Control': 'public, max-age=86400, stale-while-revalidate=604800'
        }
      });
    }
    // Bỏ qua các tệp tĩnh (CSS, JS, hình ảnh, font chữ, ads.txt, robots.txt, sitemap.xml, webp, json)
    if (url.pathname.match(/\.(css|js|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|map|txt|xml|webmanifest|webp|json)$/i) || url.pathname === '/robots.txt' || url.pathname === '/sitemap.xml' || url.pathname.startsWith('/.well-known/')) {
      const assetRes = await env.ASSETS.fetch(request);
      if (!assetRes.ok) return assetRes;
      const headers = new Headers(assetRes.headers);
      if (url.searchParams.has('v') || url.pathname.match(/\.(woff2?|ttf|ico|png|webp|jpg|jpeg|svg)$/i)) {
        headers.set('Cache-Control', 'public, max-age=31536000, immutable');
      } else {
        headers.set('Cache-Control', 'public, max-age=86400, stale-while-revalidate=604800');
      }
      return new Response(assetRes.body, {
        status: assetRes.status,
        statusText: assetRes.statusText,
        headers: headers
      });
    }

    const origin = url.origin;
    const absoluteOgImage = `${origin}/unnamed.jpg`;

    // Phục vụ trực tiếp các trang thông tin & chính sách pháp lý độc lập (AdSense & SEO compliance)
    const staticPageMap = {
      '/privacy': '/privacy.html',
      '/privacy/': '/privacy.html',
      '/terms': '/terms.html',
      '/terms/': '/terms.html',
      '/about': '/about.html',
      '/about/': '/about.html',
      '/contact': '/contact.html',
      '/contact/': '/contact.html',
      '/canvas': '/canvas.html',
      '/canvas/': '/canvas.html',
      '/cam-nang': '/cam-nang.html',
      '/cam-nang/': '/cam-nang.html'
    };

    const targetStaticFile = staticPageMap[url.pathname.toLowerCase()];
    if (targetStaticFile) {
      const pageAssetUrl = new URL(request.url);
      pageAssetUrl.pathname = targetStaticFile;
      pageAssetUrl.search = '';
      const pageRes = await env.ASSETS.fetch(new Request(pageAssetUrl.toString(), request));
      if (pageRes.ok) {
        const headers = new Headers(pageRes.headers);
        headers.set('Content-Type', 'text/html; charset=utf-8');
        headers.set('Cache-Control', 'public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800');
        return new Response(pageRes.body, {
          status: 200,
          headers: headers
        });
      }
    }

    // Xử lý các bài viết cẩm nang giáo dục độc lập (/cam-nang/:slug)
    if (url.pathname.toLowerCase().startsWith('/cam-nang/')) {
      const slugMatch = url.pathname.match(/^\/cam-nang\/([^\/?#]+)/i);
      if (slugMatch && slugMatch[1]) {
        const cleanSlug = decodeURIComponent(slugMatch[1]).replace(/\.html$/i, '').trim();
        const articleAssetUrl = new URL(request.url);
        articleAssetUrl.pathname = `/cam-nang/${cleanSlug}.html`;
        articleAssetUrl.search = '';
        const articleRes = await env.ASSETS.fetch(new Request(articleAssetUrl.toString(), request));
        if (articleRes.ok) {
          const headers = new Headers(articleRes.headers);
          headers.set('Content-Type', 'text/html; charset=utf-8');
          headers.set('Cache-Control', 'public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800');
          return new Response(articleRes.body, {
            status: 200,
            headers: headers
          });
        }
      }
    }

    // 1b. Xử lý riêng cho Studio Xuất bản Word/PDF (/export, /export/*, /export.html)
    const isExportRoute = url.pathname === '/export' || url.pathname.startsWith('/export/') || url.pathname === '/export.html';
    if (isExportRoute) {
      let exportQuizId = url.searchParams.get('id') || url.searchParams.get('quiz_id');
      if (!exportQuizId) {
        const exportMatch = url.pathname.match(/^\/export\/([^\/?#]+)/);
        if (exportMatch && exportMatch[1]) {
          exportQuizId = decodeURIComponent(exportMatch[1]);
        }
      }

      const exportAssetUrl = new URL(request.url);
      exportAssetUrl.pathname = '/export.html';
      exportAssetUrl.search = '';
      let exportResponse = await env.ASSETS.fetch(new Request(exportAssetUrl.toString(), request));
      if (!exportResponse.ok) {
        exportAssetUrl.pathname = '/export';
        exportResponse = await env.ASSETS.fetch(new Request(exportAssetUrl.toString(), request));
      }
      if (!exportResponse.ok) {
        exportResponse = await env.ASSETS.fetch(request);
      }

      const exportContentType = exportResponse.headers.get('content-type') || '';
      if (!exportResponse.ok || !exportContentType.includes('text/html')) {
        return exportResponse;
      }

      if (!exportQuizId) {
        const exportHeaders = new Headers(exportResponse.headers);
        exportHeaders.set('Cache-Control', 'public, max-age=300, s-maxage=3600, stale-while-revalidate=86400');
        return new Response(exportResponse.body, {
          status: exportResponse.status,
          statusText: exportResponse.statusText,
          headers: exportHeaders
        });
      }

      try {
        const backendUrl = `https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app/api/get_quiz/${encodeURIComponent(exportQuizId)}`;
        const backendRes = await fetch(backendUrl, {
          headers: { 'User-Agent': 'Cloudflare-Pages-Edge/1.0' }
        });
        if (backendRes.ok) {
          const quizData = await backendRes.json();
          const quizTitle = quizData.title || (quizData.data && quizData.data.title) || `Đề thi #${exportQuizId}`;
          const pageTitle = `Xuất bản: ${quizTitle} - HocNhanhTN`;
          return new HTMLRewriter()
            .on('title', { element(el) { el.setInnerContent(pageTitle); } })
            .on('meta[property="og:title"]', { element(el) { el.setAttribute('content', pageTitle); } })
            .on('meta[name="twitter:title"]', { element(el) { el.setAttribute('content', pageTitle); } })
            .on('meta[property="og:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
            .on('meta[property="og:image:secure_url"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
            .on('meta[name="twitter:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
            .on('meta[property="og:url"]', { element(el) { el.setAttribute('content', url.href); } })
            .transform(exportResponse);
        }
      } catch (e) {}

      return new HTMLRewriter()
        .on('meta[property="og:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
        .on('meta[property="og:image:secure_url"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
        .on('meta[name="twitter:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
        .on('meta[property="og:url"]', { element(el) { el.setAttribute('content', url.href); } })
        .transform(exportResponse);
    }

    // 1. Xử lý riêng cho Studio Soát lỗi & Biên tập (/editor, /editor/*, /editor.html)
    const isEditorRoute = url.pathname === '/editor' || url.pathname.startsWith('/editor/') || url.pathname === '/editor.html';
    if (isEditorRoute) {
      let editorQuizId = url.searchParams.get('id') || url.searchParams.get('quiz_id');
      if (!editorQuizId) {
        const editorMatch = url.pathname.match(/^\/editor\/([^\/?#]+)/);
        if (editorMatch && editorMatch[1]) {
          editorQuizId = decodeURIComponent(editorMatch[1]);
        }
      }

      // Luôn tải đúng editor.html từ Cloudflare Pages ASSETS
      const editorAssetUrl = new URL(request.url);
      editorAssetUrl.pathname = '/editor.html';
      editorAssetUrl.search = '';
      let editorResponse = await env.ASSETS.fetch(new Request(editorAssetUrl.toString(), request));
      if (!editorResponse.ok) {
        editorAssetUrl.pathname = '/editor';
        editorResponse = await env.ASSETS.fetch(new Request(editorAssetUrl.toString(), request));
      }
      if (!editorResponse.ok) {
        editorResponse = await env.ASSETS.fetch(request);
      }

      const editorContentType = editorResponse.headers.get('content-type') || '';
      if (!editorResponse.ok || !editorContentType.includes('text/html')) {
        return editorResponse;
      }

      if (!editorQuizId) {
        const editorHeaders = new Headers(editorResponse.headers);
        editorHeaders.set('Cache-Control', 'public, max-age=300, s-maxage=3600, stale-while-revalidate=86400');
        return new Response(editorResponse.body, {
          status: editorResponse.status,
          statusText: editorResponse.statusText,
          headers: editorHeaders
        });
      }

      // Có mã đề thi: Edge Worker truy vấn máy chủ Koyeb để lấy tên đề thi thực tế
      try {
        const backendUrl = `https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app/api/get_quiz/${encodeURIComponent(editorQuizId)}`;
        const backendRes = await fetch(backendUrl, {
          headers: { 'User-Agent': 'Cloudflare-Pages-Edge/1.0' }
        });
        if (backendRes.ok) {
          const quizData = await backendRes.json();
          if (quizData.status === 'success' && quizData.title) {
            const rawTitle = quizData.title.trim();
            const pageTitle = `Soát lỗi đề: ${rawTitle} - HocNhanhTN`;
            return new HTMLRewriter()
              .on('title', { element(el) { el.setInnerContent(pageTitle); } })
              .on('meta[property="og:title"]', { element(el) { el.setAttribute('content', pageTitle); } })
              .on('meta[name="twitter:title"]', { element(el) { el.setAttribute('content', pageTitle); } })
              .on('meta[property="og:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
              .on('meta[property="og:image:secure_url"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
              .on('meta[name="twitter:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
              .on('meta[property="og:url"]', { element(el) { el.setAttribute('content', url.href); } })
              .transform(editorResponse);
          }
        }
      } catch (err) {}

      return new HTMLRewriter()
        .on('meta[property="og:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
        .on('meta[property="og:image:secure_url"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
        .on('meta[name="twitter:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
        .on('meta[property="og:url"]', { element(el) { el.setAttribute('content', url.href); } })
        .transform(editorResponse);
    }

    const quizId = url.searchParams.get('id') || url.searchParams.get('quiz_id');
    
    let targetQuizId = quizId;
    let isLeaderboard = false;
    if (!targetQuizId) {
      const match = url.pathname.match(/^\/(quiz|thi|xep-hang)\/([^\/?#]+)/i);
      if (match) {
        targetQuizId = decodeURIComponent(match[2]);
        if (match[1].toLowerCase() === 'xep-hang') {
          isLeaderboard = true;
        }
      }
    }
    if (targetQuizId) {
      targetQuizId = targetQuizId.replace(/\.html$/i, '').trim();
    }

    // Tải tệp HTML gốc từ bộ nhớ đệm Cloudflare Pages
    let response = await env.ASSETS.fetch(request);
    let contentType = response.headers.get('content-type') || '';
    
    // Nếu yêu cầu đường dẫn con (/thi/ROC-362, /thi/ROC-362/slug, /xep-hang/...) mà Pages không khớp file vật lý, tải fallback /index.html
    if (!response.ok || !contentType.includes('text/html')) {
      const indexAssetUrl = new URL(request.url);
      indexAssetUrl.pathname = '/index.html';
      indexAssetUrl.search = '';
      const fallbackResponse = await env.ASSETS.fetch(new Request(indexAssetUrl.toString(), request));
      if (fallbackResponse.ok) {
        response = fallbackResponse;
        contentType = response.headers.get('content-type') || '';
      }
    }

    if (!response.ok || !contentType.includes('text/html')) {
      return response;
    }

    // Nếu không có mã đề thi (trang chủ / landing page tĩnh), trả về HTML trực tiếp với cache Edge để tối ưu TTFB
    if (!targetQuizId) {
      const homeHeaders = new Headers(response.headers);
      homeHeaders.set('Cache-Control', 'public, max-age=300, s-maxage=3600, stale-while-revalidate=86400');
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: homeHeaders
      });
    }

    // Khi có mã đề thi: Edge Worker truy vấn máy chủ Koyeb để lấy tên đề thi thực tế
    try {
      const backendUrl = `https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app/api/get_quiz/${encodeURIComponent(targetQuizId)}`;
      const backendRes = await fetch(backendUrl, {
        headers: { 'User-Agent': 'Cloudflare-Pages-Edge/1.0' }
      });
      if (backendRes.ok) {
        const quizData = await backendRes.json();
        if (quizData.status === 'success' && quizData.title) {
          const rawTitle = quizData.title.trim();
          const pageTitle = isLeaderboard
            ? `Bảng xếp hạng: ${rawTitle} (#${targetQuizId}) - HocNhanhTN`
            : `${rawTitle} - HocNhanhTN`;
          const ogTitle = isLeaderboard ? `Bảng xếp hạng: ${rawTitle}` : rawTitle;
          const qCount = Array.isArray(quizData.data) ? quizData.data.length : 0;
          const timeLimit = quizData.time_limit || 0;
          
          let desc = isLeaderboard
            ? `Xem bảng vinh danh và kết quả bài thi ${rawTitle} (#${targetQuizId}) tại HocNhanhTN.`
            : `Đề thi: ${rawTitle}`;
          if (!isLeaderboard) {
            if (qCount > 0) desc += ` • ${qCount} câu hỏi`;
            if (timeLimit > 0) desc += ` • ${timeLimit} phút làm bài`;
            desc += `. Hệ thống học nhanh trắc nghiệm chuẩn GDPT 2018 trên HocNhanhTN.`;
          }

          return new HTMLRewriter()
            .on('title', { element(el) { el.setInnerContent(pageTitle); } })
            .on('meta[property="og:title"]', { element(el) { el.setAttribute('content', ogTitle); } })
            .on('meta[name="twitter:title"]', { element(el) { el.setAttribute('content', ogTitle); } })
            .on('meta[name="description"]', { element(el) { el.setAttribute('content', desc); } })
            .on('meta[property="og:description"]', { element(el) { el.setAttribute('content', desc); } })
            .on('meta[name="twitter:description"]', { element(el) { el.setAttribute('content', desc); } })
            .on('meta[property="og:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
            .on('meta[property="og:image:secure_url"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
            .on('meta[name="twitter:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
            .on('meta[property="og:url"]', { element(el) { el.setAttribute('content', url.href); } })
            .transform(response);
        }
      }
    } catch (err) {
      // Nếu có lỗi kết nối backend, dùng fallback title
    }

    const fallbackTitle = isLeaderboard
      ? `Bảng xếp hạng #${targetQuizId} - HocNhanhTN`
      : `Phòng thi trực tuyến #${targetQuizId} - HocNhanhTN`;

    return new HTMLRewriter()
      .on('title', { element(el) { el.setInnerContent(fallbackTitle); } })
      .on('meta[property="og:title"]', { element(el) { el.setAttribute('content', fallbackTitle); } })
      .on('meta[name="twitter:title"]', { element(el) { el.setAttribute('content', fallbackTitle); } })
      .on('meta[property="og:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
      .on('meta[property="og:image:secure_url"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
      .on('meta[name="twitter:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
      .on('meta[property="og:url"]', { element(el) { el.setAttribute('content', url.href); } })
      .transform(response);
  }
};
