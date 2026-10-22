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
      const llmsContent = `# HocNhanhTN\n\n> Hệ thống học nhanh trắc nghiệm thông minh cho học sinh & giáo viên - Chuẩn GDPT 2018.\n\nHocNhanhTN là nền tảng số hóa đề thi Word (.docx) và PDF thành phòng thi trực tuyến chuẩn Chương trình Giáo dục phổ thông 2018, tự động nhận diện công thức Toán Lý Hóa (LaTeX) và hình ảnh minh họa.\n\n## Tính năng & Liên kết chính\n- [Trang chủ HocNhanhTN](https://hocnhanhtn.online/): Nền tảng số hóa và tổ chức phòng thi trực tuyến.\n- [Quy trình số hóa đề thi](https://hocnhanhtn.online/#quy-trinh): Tự động nhận diện công thức Toán Lý Hóa và hình ảnh minh họa.\n- [Định dạng chuẩn GDPT 2018](https://hocnhanhtn.online/#dang-thuc-gdpt): Trắc nghiệm nhiều lựa chọn, đúng sai, trả lời ngắn.\n- [Studio Biên tập Đề thi](https://hocnhanhtn.online/editor): Giao diện biên soạn và soát lỗi đề thi trực quan.\n- [Chính sách bảo mật](https://hocnhanhtn.online/#privacy): Cam kết bảo vệ quyền riêng tư người dùng.\n- [Điều khoản dịch vụ](https://hocnhanhtn.online/#terms): Quy định dịch vụ và bản quyền học liệu.\n`;
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
    const quizId = url.searchParams.get('id') || url.searchParams.get('quiz_id');
    
    let targetQuizId = quizId;
    if (!targetQuizId) {
      const match = url.pathname.match(/^\/quiz\/([^\/]+)/);
      if (match) targetQuizId = match[1];
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

    // Tải tệp HTML gốc từ bộ nhớ đệm Cloudflare Pages
    let response = await env.ASSETS.fetch(request);
    const contentType = response.headers.get('content-type') || '';
    if (!response.ok || !contentType.includes('text/html')) {
      return response;
    }

    const origin = url.origin;
    const absoluteOgImage = `${origin}/unnamed.jpg`;

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
      const backendUrl = `https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app/api/get_quiz/${targetQuizId}`;
      const backendRes = await fetch(backendUrl, {
        headers: { 'User-Agent': 'Cloudflare-Pages-Edge/1.0' }
      });
      if (backendRes.ok) {
        const quizData = await backendRes.json();
        if (quizData.status === 'success' && quizData.title) {
          const rawTitle = quizData.title.trim();
          const pageTitle = `${rawTitle} - HocNhanhTN`;
          const qCount = Array.isArray(quizData.data) ? quizData.data.length : 0;
          const timeLimit = quizData.time_limit || 0;
          
          let desc = `Đề thi: ${rawTitle}`;
          if (qCount > 0) desc += ` • ${qCount} câu hỏi`;
          if (timeLimit > 0) desc += ` • ${timeLimit} phút làm bài`;
          desc += `. Hệ thống học nhanh trắc nghiệm chuẩn GDPT 2018 trên HocNhanhTN.`;

          return new HTMLRewriter()
            .on('title', { element(el) { el.setInnerContent(pageTitle); } })
            .on('meta[property="og:title"]', { element(el) { el.setAttribute('content', rawTitle); } })
            .on('meta[name="twitter:title"]', { element(el) { el.setAttribute('content', rawTitle); } })
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
      // Nếu có lỗi kết nối backend, trả về HTML mặc định với ảnh tuyệt đối
    }

    return new HTMLRewriter()
      .on('meta[property="og:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
      .on('meta[property="og:image:secure_url"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
      .on('meta[name="twitter:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
      .on('meta[property="og:url"]', { element(el) { el.setAttribute('content', url.href); } })
      .transform(response);
  }
};
